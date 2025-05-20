from flask import Flask, request, jsonify, send_file, render_template 
import os, subprocess, glob, datetime 
from shortuuid import uuid
from splat import ply_to_splat
from v_utils import split_video
from threading import Thread, Lock, Condition
import telebot

app = Flask(__name__)
app.config['THREADS'] = True

token = os.getenv('TG_TOKEN')
if not token: 
    print('bot token needed for tg integration...')
    quit()

bot = telebot.TeleBot(token)

BASE_DIR = token = os.getenv('BASE_DIR')
SPLAT_DIR = token = os.getenv('SPLAT_DIR')
VIEW_URL = token = os.getenv('VIEW_URL')

tasks_lock = Lock()
gaussing_lock = Lock()
gaussing_condition = Condition(gaussing_lock)
gaussing_queue = []
current_gaussing = None

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message,"Пришли видео (не больше 20 Мб) и через время получишь ссылку на splat")


@bot.message_handler(content_types=['video'])
def process_video(message):
    try:
        task_id = uuid()
        current = os.path.join(BASE_DIR, task_id)
        os.makedirs(current, exist_ok=True)
        fl_name = message.video.file_unique_id + '.mp4'
        file_info = bot.get_file(message.video.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        input_file_path = os.path.join(current, fl_name)
        with open(input_file_path, 'wb') as f: 
            f.write(downloaded_file)
        with open(os.path.join(current, 'filename'), 'w') as f:
            f.write(fl_name)
        with open(os.path.join(current, 'chat_id'), 'w') as f:
            f.write(str(message.chat.id))
        with open(os.path.join(current, 'created_at'), 'w') as f:
            f.write(datetime.datetime.now().isoformat())
        update_status(task_id, 'created')
        
        thread = Thread(target=split_task, args=(task_id, ))
        thread.start()

        bot.reply_to(message,"Начал обработку, вернусь позже...")
    except Exception as e:
        bot.reply_to(message, str(e))


# Инициализация задач при запуске
def init_tasks():
    tasks = {}
    for task_dir in glob.glob(os.path.join(BASE_DIR, '*')):
        if os.path.isdir(task_dir):
            task_id = os.path.basename(task_dir)
            status_file = os.path.join(task_dir, 'status')
            if os.path.exists(status_file):
                with open(status_file, 'r') as f:
                    status = f.read().strip()
                error_file = os.path.join(task_dir, 'error')
                error = ''
                if os.path.exists(error_file):
                    with open(error_file, 'r') as f:
                        error = f.read()
                created_at_file = os.path.join(task_dir, 'created_at')
                created_at = 'N/A'
                if os.path.exists(created_at_file):
                    with open(created_at_file, 'r') as f:
                        created_at = f.read()
                tasks[task_id] = {'status': status, 'error': error, 'created_at': created_at}
    return tasks


tasks = init_tasks()


def update_status(task_id, status, error=''): 
    task_dir = os.path.join(BASE_DIR, task_id)
    status_file = os.path.join(task_dir, 'status')
    with open(status_file, 'w') as f:
        f.write(status)
    if error:
        error_file = os.path.join(task_dir, 'error')
        with open(error_file, 'w') as f:
            f.write(error)
    else:
        error_file = os.path.join(task_dir, 'error')
        if os.path.exists(error_file):
            os.remove(error_file)
    with tasks_lock:
        tasks[task_id] = {'status': status, 'error': error}


@app.route('/process', methods=['POST'])
def process_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400
        
    file = request.files['file']
    
    try:
        task_id = uuid()
        current = os.path.join(BASE_DIR, task_id)
        os.makedirs(current, exist_ok=True)
        input_file_path = os.path.join(current, file.filename)
        file.save(input_file_path)
        with open(os.path.join(current, 'filename'), 'w') as f:
            f.write(file.filename)
        with open(os.path.join(current, 'created_at'), 'w') as f:
            f.write(datetime.datetime.now().isoformat())
        update_status(task_id, 'created')

        thread = Thread(target=split_task, args=(task_id, ))
        thread.start()
        
        return jsonify({'task_id': task_id}), 202
        
    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500


def split_task(task_id):
    current = os.path.join(BASE_DIR, task_id)
    file4file = os.path.join(current, 'filename')
    try:
        with open(file4file, 'r') as f:
            input_file_path = os.path.join(current, f.read())
        update_status(task_id, 'split')
        input_dir = os.path.join(current, 'input')
        os.makedirs(input_dir, exist_ok=True)
        split_video(input_file_path, input_dir)
        update_status(task_id, 'split_complete')
        
        thread = Thread(target=convert_task, args=(task_id, ))
        thread.start()
        
    except Exception as e:
        update_status(task_id, 'split_error', str(e))


def convert_task(task_id):
    global current_gaussing
    current = os.path.join(BASE_DIR, task_id)
    try:
        update_status(task_id, 'convert')
        convert_cmd = ['python', 'convert.py', '-s', current]
        subprocess.run(convert_cmd, check=True)
        update_status(task_id, 'convert_complete')
        
        with gaussing_condition:
            if not current_gaussing:
                thread = Thread(target=gaussing_task, args=(task_id, ))
                thread.start()
                current_gaussing = task_id
            else:
                update_status(task_id, 'waiting')
                gaussing_queue.append((task_id, ))
        
    except Exception as e:
        update_status(task_id, 'convert_error', str(e))


def gaussing_task(task_id):
    global current_gaussing
    current = os.path.join(BASE_DIR, task_id)
    try:
        update_status(task_id, 'gaussing')
        output = os.path.join(current, 'output')
        subprocess.run(['python', 'train.py', '-s', current, '--model_path', output], check=True)
        update_status(task_id, 'gaussing_complete')
        
        thread = Thread(target=splatting_task, args=(task_id, ))
        thread.start()
        
    except Exception as e:
        update_status(task_id, 'gaussing_error', str(e))
    finally:
        with gaussing_condition:
            current_gaussing = None
            if gaussing_queue:
                next_task = gaussing_queue.pop(0)
                current_gaussing = next_task[0]
                thread = Thread(target=gaussing_task, args=next_task)
                thread.start()


def splatting_task(task_id):
    current = os.path.join(BASE_DIR, task_id)
    try:
        update_status(task_id, 'splatting')
        output = os.path.join(current, 'output')
        ply_file = os.path.join(output, 'point_cloud', 'iteration_30000', 'point_cloud.ply')
        if not os.path.exists(ply_file):
            update_status(task_id, 'error', 'PLY file not found')
            return
            
        splat_path = os.path.join(SPLAT_DIR, f"{task_id}.splat") #os.path.join(output, "output.splat")
        with open(splat_path, "wb") as f:
            f.write(ply_to_splat(ply_file))
            
        update_status(task_id, 'completed')
        file4chat_id = os.path.join(current, 'chat_id')
        if os.path.exists(file4chat_id):
            with open(file4chat_id, 'r') as f:
                bot.send_message(f.read(), VIEW_URL.format(task_id))
            
    except Exception as e:
        update_status(task_id, 'error', str(e))


@app.route('/')
def index():
    return render_template('index.html') # app.send_static_file('index.html')


@app.route('/status/<task_id>')
def check_status(task_id):
    task_dir = os.path.join(BASE_DIR, task_id)
    if not os.path.exists(task_dir):
        return jsonify({'status': 'not_found'}), 404
        
    # Получаем информацию о задаче
    status_file = os.path.join(task_dir, 'status')
    error_file = os.path.join(task_dir, 'error')
    created_at_file = os.path.join(task_dir, 'created_at')
    
    status = open(status_file, 'r').read().strip() if os.path.exists(status_file) else 'unknown'
    error = open(error_file, 'r').read() if os.path.exists(error_file) else ''
    created_at = open(created_at_file, 'r').read() if os.path.exists(created_at_file) else 'N/A'
    
    return jsonify({
        'task_id': task_id,
        'status': status,
        'error': error,
        'created_at': created_at
    })


@app.route('/tasks')
def list_tasks():
    result = []
    for task_dir in glob.glob(os.path.join(BASE_DIR, '*')):
        if os.path.isdir(task_dir):
            task_id = os.path.basename(task_dir)
            status_file = os.path.join(task_dir, 'status')
            if os.path.exists(status_file):
                with open(status_file, 'r') as f:
                    status = f.read().strip()
                if status == 'deleted':  # Исключаем удаленные задачи
                    continue
                error_file = os.path.join(task_dir, 'error')
                error = ''
                if os.path.exists(error_file):
                    with open(error_file, 'r') as f:
                        error = f.read()
                created_at_file = os.path.join(task_dir, 'created_at')
                created_at = 'N/A'
                if os.path.exists(created_at_file):
                    with open(created_at_file, 'r') as f:
                        created_at = f.read()
                # Добавляем URL если задача завершена
                splat_path = os.path.join(SPLAT_DIR, f"{task_id}.splat")
                url = VIEW_URL.format(task_id) if os.path.exists(splat_path) else None
                
                result.append({
                    'task_id': task_id, 
                    'status': status, 
                    'error': error,
                    'created_at': created_at,
                    'url': url
                })
    return jsonify(result)


@app.route('/split/<task_id>')
def manual_split(task_id):
    try:
        thread = Thread(target=split_task, args=(task_id, ))
        thread.start()
        return jsonify({'task_id': task_id,"status":"split"}), 202
        
    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500


@app.route('/convert/<task_id>')
def manual_convert(task_id):
    try:
        thread = Thread(target=convert_task, args=(task_id, ))
        thread.start()
        return jsonify({'task_id': task_id,"status":"convert"}), 202
        
    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500


@app.route('/gaussing/<task_id>')
def manual_gaussing(task_id):
    global current_gaussing
    try:
        with gaussing_condition:
            if not current_gaussing:
                thread = Thread(target=gaussing_task, args=(task_id, ))
                thread.start()
                current_gaussing = task_id
                return jsonify({'task_id': task_id,"status":"gaussing"}), 202
            else:
                update_status(task_id, 'waiting')
                gaussing_queue.append((task_id, ))
                return jsonify({'task_id': task_id,"status":"waiting"}), 202
        
    except Exception as e:
        update_status(task_id, 'convert_error', str(e))


@app.route('/splatting/<task_id>')
def manual_splatting(task_id):
    try:
        thread = Thread(target=splatting_task, args=(task_id, ))
        thread.start()
        return jsonify({'task_id': task_id,"status":"splatting"}), 202
        
    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500


@app.route('/delete/<task_id>')
def delete_task(task_id):
    task_dir = os.path.join(BASE_DIR, task_id)
    if not os.path.exists(task_dir):
        return jsonify({'error': 'Task not found'}), 404
    
    update_status(task_id, 'deleted')
    return jsonify({'status': 'deleted'})


@app.route('/download/<task_id>')
def download_ply(task_id):
    task_dir = os.path.join(BASE_DIR, task_id)
    ply_path = os.path.join(task_dir, 'output', 'point_cloud', 'iteration_30000', 'point_cloud.ply')
    
    if not os.path.exists(ply_path):
        return jsonify({'error': 'File not found'}), 404
        
    return send_file(ply_path, as_attachment=True, download_name='point_cloud.ply')


@app.route('/rename/<task_id>', methods=['POST'])
def rename_task(task_id):
    task_dir = os.path.join(BASE_DIR, task_id)
    if not os.path.exists(task_dir):
        return jsonify({'error': 'Task not found'}), 404
    
    data = request.json
    if 'new_task_id' not in data:
        return jsonify({'error': 'New task ID not provided'}), 400
    
    new_task_id = data['new_task_id']
    new_task_dir = os.path.join(BASE_DIR, new_task_id)
    
    if os.path.exists(new_task_dir):
        return jsonify({'error': 'New task ID already exists'}), 400
    
    try:
        os.rename(task_dir, new_task_dir)
        
        # Update related files and status
        splat_path = os.path.join(SPLAT_DIR, f"{task_id}.splat")
        new_splat_path = os.path.join(SPLAT_DIR, f"{new_task_id}.splat")
        if os.path.exists(splat_path):
            os.rename(splat_path, new_splat_path)
        
        # Update tasks dictionary
        with tasks_lock:
            task_info = tasks.pop(task_id, None)
            if task_info:
                tasks[new_task_id] = task_info
        
        return jsonify({'task_id': new_task_id, 'status': 'renamed'}), 200
    
    except Exception as e:
        return jsonify({"error": f"Failed to rename task: {str(e)}"}), 500


def run_telegram_bot():
    with app.app_context():  # Устанавливаем контекст Flask-приложения
        bot.infinity_polling()

# Запускаем Telegram-бота в отдельном потоке
Thread(
    target=run_telegram_bot,
    name='bot_infinity_polling',
    daemon=True
).start()

if __name__ == '__main__':
    with app.app_context():
        app.run(debug=True, host='0.0.0.0', port=5000, threaded=True)