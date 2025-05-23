document.addEventListener('DOMContentLoaded', function () {
    const uploadForm = document.getElementById('uploadForm');
    const uploadStatus = document.getElementById('uploadStatus');
    const tasksTableBody = document.querySelector('#tasksTable tbody');

    window. deleteTask = function(taskId) {
        if (confirm('Удалить задачу?')) {
            fetch(`/delete/${taskId}`)
                .then(response => response.json())
                .then(data => {
                    alert('Задача удалена');
                    fetchTasks();
                });
        }
    }
    
    window.downloadPly = function(taskId) {
        window.open(`/download/${taskId}`);
    }

    window.renameTask = function(taskId, newTaskId) {
        fetch(`/rename/${taskId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ new_task_id: newTaskId })
        })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'renamed') {
                    alert('Задача переименована');
                    fetchTasks();
                } else {
                    alert(`Ошибка: ${data.error}`);
                }
            })
            .catch(error => {
                alert(`Ошибка: ${error}`);
            });
    }

    function fetchTasks() {
        fetch('/tasks')
            .then(response => response.json())
            .then(tasks => {
                tasksTableBody.innerHTML = '';
                tasks.forEach(task => {
                    const row = document.createElement('tr');
                    row.innerHTML = `
                        <td>${task.task_id}</td>
                        <td>${task.created_at}</td>
                        <td>${task.status}</td>
                        <td>${task.status === 'completed' ? `
                            <a href="#" onclick="showInViewer('${task.url}')">Посмотреть</a>
                            <a href="#" onclick="showInViewer('https://wald.beirel.ru:44443/splat/?url=splats/${task.task_id}_crop.splat#')">Croped</a>
                        ` : ''}</td> 
                        <td>
                        ${task.status === 'completed' ? `
                            <input type="range" class="quantile-slider" min="0.1" max="0.9" step="0.05" value="0.25" data-task-id="${task.task_id}">
                            <button onclick="cropSplat('${task.task_id}')">CROP</button>
                        ` : ''}
                            <button onclick="manualSplit('${task.task_id}')">Split</button>
                            <button onclick="manualConvert('${task.task_id}')">Convert</button>
                            <button onclick="manualGaussing('${task.task_id}')">Gaussing</button>
                            <button onclick="manualSplatting('${task.task_id}')">Splatting</button>
                            <button onclick="deleteTask('${task.task_id}')" style="color: red">Удалить</button>
                            ${task.url ? `<button onclick="downloadPly('${task.task_id}')">Скачать PLY</button>` : ''}
                            <input type="text" id="newTaskId_${task.task_id}" placeholder="${task.task_id}"> 
                            <button onclick="renameTask('${task.task_id}', document.getElementById('newTaskId_${task.task_id}').value)">Переименовать</button>
                        </td>
                    `;
                    tasksTableBody.appendChild(row);
                });
            });
    }

    // Добавим функцию для управления фреймом
    window.showInViewer = function(url){
        const viewer = document.getElementById('splatViewer');
        viewer.src = url;
        
        // Дополнительно: кнопка закрытия
        if (!document.querySelector('.close-viewer-btn')) {
            const closeBtn = document.createElement('button');
            closeBtn.className = 'close-viewer-btn';
            closeBtn.innerHTML = '× Закрыть';
            closeBtn.style.position = 'absolute';
            closeBtn.style.right = '20px';
            closeBtn.style.top = '20px';
            closeBtn.onclick = () => {
                viewer.src = '';
                closeBtn.remove();
            }
            document.querySelector('.viewer-section').appendChild(closeBtn);
        }
    }

    uploadForm.addEventListener('submit', function (e) {
        e.preventDefault();
        const formData = new FormData(uploadForm);
        fetch('/process', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            uploadStatus.textContent = `Задача создана: ${data.task_id}`;
            fetchTasks();
        })
        .catch(error => {
            uploadStatus.textContent = `Ошибка: ${error}`;
        });
    });

    window.manualSplit = function(taskId) {
        fetch(`/split/${taskId}`)
            .then(response => response.json())
            .then(data => alert(data.status));
    }

    window.manualConvert = function(taskId) {
        fetch(`/convert/${taskId}`)
            .then(response => response.json())
            .then(data => alert(data.status));
    }

     window.manualGaussing = function(taskId) {
        fetch(`/gaussing/${taskId}`)
            .then(response => response.json())
            .then(data => alert(data.status));
    }

    window.manualSplatting = function(taskId) {
        fetch(`/splatting/${taskId}`)
            .then(response => response.json())
            .then(data => alert(data.status));
    }

    window.cropSplat = function(taskId) {
        const quantile = document.querySelector(`input[data-task-id="${taskId}"].quantile-slider`).value;
        
        fetch(`/splatting/${taskId}/crop?quantile=${quantile}`)
            .then(response => response.json())
            .then(data => alert(data.status))
            .catch(error => console.error('Error:', error));
    }
    // Обновление задач каждые 60 секунд
    setInterval(fetchTasks, 60000);
    fetchTasks();
});