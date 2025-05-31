document.addEventListener('DOMContentLoaded', function() {
    // Elementos de la interfaz
    const dropArea = document.getElementById('dropArea');
    const fileInput = document.getElementById('fileInput');
    const progressContainer = document.getElementById('progressContainer');
    const progressBar = document.getElementById('progressBar');
    const progressText = document.getElementById('progressText');
    const statusText = document.getElementById('statusText');
    const downloadArea = document.getElementById('downloadArea');
    const downloadBtn = document.getElementById('downloadBtn');
    const lmstudioUrl = document.getElementById('lmstudio_url');
    const lmstudioPort = document.getElementById('lmstudio_port');
    let eventSource = null; // Para almacenar la conexión SSE
    
    // Prevenir comportamientos por defecto de arrastrar y soltar
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropArea.addEventListener(eventName, preventDefaults, false);
        document.body.addEventListener(eventName, preventDefaults, false);
    });
    
    // Resaltar área de soltar cuando se arrastra sobre ella
    ['dragenter', 'dragover'].forEach(eventName => {
        dropArea.addEventListener(eventName, highlight, false);
    });
    
    ['dragleave', 'drop'].forEach(eventName => {
        dropArea.addEventListener(eventName, unhighlight, false);
    });
    
    // Manejar archivos soltados
    dropArea.addEventListener('drop', handleDrop, false);
    
    // Manejar clic para seleccionar archivo
    dropArea.addEventListener('click', () => {
        fileInput.click();
    });
    
    // Manejar selección de archivo
    fileInput.addEventListener('change', handleFiles);
    
    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }
    
    function highlight() {
        dropArea.style.borderColor = '#4a90e2';
        dropArea.style.backgroundColor = 'rgba(74, 144, 226, 0.1)';
    }
    
    function unhighlight() {
        dropArea.style.borderColor = '#ddd';
        dropArea.style.backgroundColor = '';
    }
    
    function handleDrop(e) {
        const dt = e.dataTransfer;
        const files = dt.files;
        
        if (files.length) {
            handleFiles({ target: { files: files } });
        }
    }
    
    function handleFiles(e) {
        const files = e.target.files;
        if (files.length === 0) return;
        
        const file = files[0];
        if (!file.name.endsWith('.srt')) {
            showError('Por favor, selecciona un archivo .srt');
            return;
        }
        
        uploadFile(file);
    }
    
    function uploadFile(file) {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('lmstudio_url', lmstudioUrl.value);
        formData.append('lmstudio_port', lmstudioPort.value);
        formData.append('lines_per_batch', document.getElementById('lines_per_batch').value);
        
        // Mostrar contenedor de progreso
        resetUI();
        progressContainer.style.display = 'block';
        progressBar.style.width = '0%';
        progressText.textContent = '0%';
        statusText.textContent = 'Iniciando...';
        
        // Enviar el archivo
        fetch('/upload', {
            method: 'POST',
            body: formData
        })
        .then(response => {
            if (!response.ok) {
                return response.json().then(err => { throw new Error(err.error || 'Error en el servidor'); });
            }
            return response.json();
        })
        .then(data => {
            if (data.error) {
                throw new Error(data.error);
            }
            
            // Iniciar el seguimiento del progreso
            trackProgress(data.task_id, data.output_filename);
            downloadBtn.href = data.download_url;
            
            // Reiniciar el input de archivo
            fileInput.value = '';
        })
        .catch(error => {
            console.error('Error:', error);
            showError(error.message || 'Error al procesar el archivo');
        });
    }
    
    function resetUI() {
        downloadArea.style.display = 'none';
        progressBar.style.width = '0%';
        progressBar.style.backgroundColor = '#4a90e2'; // Color azul por defecto
        progressText.textContent = '0%';
        statusText.textContent = 'Preparando...';
    }
    
    function showError(message) {
        statusText.textContent = message;
        statusText.style.color = 'red';
        progressBar.style.backgroundColor = '#f44336';
    }
    
    function trackProgress(taskId, outputFilename) {
        // Cerrar cualquier conexión anterior
        if (eventSource) {
            eventSource.close();
        }
        
        // Crear nueva conexión SSE
        eventSource = new EventSource(`/progress/${taskId}`);
        
        eventSource.onmessage = function(event) {
            try {
                const data = JSON.parse(event.data);
                
                if (data.error) {
                    showError(data.error);
                    eventSource.close();
                    return;
                }
                
                // Actualizar la barra de progreso
                const progress = data.progress || 0;
                progressBar.style.width = `${progress}%`;
                progressText.textContent = `${progress}%`;
                statusText.textContent = data.status || 'Procesando...';
                
                // Si la tarea está completa o hay un error
                if (data.complete || data.error) {
                    if (data.error) {
                        showError(data.error);
                    } else {
                        progressBar.style.backgroundColor = '#4CAF50'; // Verde al completar
                        statusText.textContent = data.status || '¡Traducción completada!';
                        
                        // Mostrar botón de descarga
                        if (outputFilename) {
                            downloadArea.style.display = 'block';
                            downloadBtn.href = `/download/${encodeURIComponent(outputFilename)}`;
                            downloadBtn.download = outputFilename;
                        }
                    }
                    
                    // Cerrar la conexión
                    if (eventSource) {
                        eventSource.close();
                        eventSource = null;
                    }
                    return;
                }
            } catch (error) {
                console.error('Error procesando mensaje SSE:', error);
                showError('Error al procesar la respuesta del servidor');
                if (eventSource) eventSource.close();
            }
        };
        
        eventSource.onerror = function() {
            // No mostrar error si la conexión se cierra normalmente
            if (eventSource.readyState === EventSource.CLOSED) {
                return;
            }
            
            showError('Error en la conexión con el servidor');
            if (eventSource) eventSource.close();
        };
    }
    
    // Manejar clic en el botón de descarga
    downloadBtn.addEventListener('click', function(e) {
        if (!this.href || this.href === '#') {
            e.preventDefault();
        }
    });
});
