from flask import Flask, request, send_file, jsonify
import os
import subprocess
import shutil
import tempfile

app = Flask(__name__)

# Базовая директория проекта
BASE_DIR = ''
DATA_DIR = ''

@app.route('/process', methods=['POST'])
def process_file():
    try:
        # Проверяем наличие файла и параметров
        if 'file' not in request.files:
            return jsonify({"error": "No file provided"}), 400
        
        file = request.files['file']
        #video_name = request.form.get('video_name', '')
        #flag = request.form.get('flag', '')  # -v, --resize или пусто

        # Создаем временную папку для данных
        # temp_dir = tempfile.mkdtemp()
        dataset_dir = os.path.join(DATA_DIR, os.path.splitext(file.filename)[0])
        input_dir = os.path.join(DATA_DIR, 'input')

        os.makedirs(dataset_dir, exist_ok=True)
        os.makedirs(os.path.join(dataset_dir), exist_ok=True)

        # Сохраняем загруженный файл
        input_file_path = os.path.join(dataset_dir, file.filename)
        file.save(input_file_path)

        # Сохраняем текущую директорию и переходим в рабочую
        current_dir = os.getcwd()
        os.chdir(BASE_DIR)

        # Выполняем команды из скрипта
        try:
            # 1. Выполнение v2f.py, если указан флаг -v
            if flag == '-v':
                subprocess.run(
                    ['uv', 'run', 'v2f.py', '-s', dataset_dir, '--video_name', video_name],
                    check=True
                )

            # 2. Выполнение convert.py
            convert_cmd = ['uv', 'run', 'convert.py', '-s', dataset_dir]
            if flag == '--resize':
                convert_cmd.append('--resize')
            subprocess.run(convert_cmd, check=True)

            # 3. Выполнение train.py
            subprocess.run(['uv', 'run', 'train.py', '-s', dataset_dir], check=True)

            # Предполагаем, что train.py создает .ply файл в dataset_dir/output/
            ply_file = os.path.join(dataset_dir, 'output', 'point_cloud.ply')  # Укажите правильный путь

            if not os.path.exists(ply_file):
                return jsonify({"error": "PLY file not found"}), 500

            # Возвращаем .ply файл
            return send_file(ply_file, as_attachment=True, download_name='point_cloud.ply')

        finally:
            # Возвращаемся в исходную директорию
            os.chdir(current_dir)
            # Удаляем временные файлы (опционально)
            # shutil.rmtree(temp_dir, ignore_errors=True)

    except subprocess.CalledProcessError as e:
        return jsonify({"error": f"Script execution failed: {str(e)}"}), 500
    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)