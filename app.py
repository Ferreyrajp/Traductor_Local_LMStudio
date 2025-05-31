from flask import Flask, render_template, request, jsonify, send_from_directory, Response, stream_with_context
import os
import re
import json
import time
import uuid
import threading
from werkzeug.utils import secure_filename
from utils.translator import process_subtitle_file
from functools import wraps
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # Habilitar CORS para SSE
app.config['UPLOAD_FOLDER'] = os.path.abspath('uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Almacenar el progreso de las tareas
tasks_progress = {}

def event_stream(task_id):
    while True:
        if task_id not in tasks_progress:
            yield f"data: {json.dumps({'error': 'Tarea no encontrada'})}\n\n"
            break
            
        progress = tasks_progress[task_id]
        
        if progress.get('complete', False):
            yield f"data: {json.dumps(progress)}\n\n"
            del tasks_progress[task_id]
            break
            
        yield f"data: {json.dumps(progress)}\n\n"
        time.sleep(0.5)

def update_progress(task_id, current, total, message, complete=False, error=None):
    progress = int((current / total) * 100) if total > 0 else 0
    tasks_progress[task_id] = {
        'progress': progress,
        'status': message,
        'complete': complete or current >= total,
        'error': error
    }
    # Si hay un error o está completo, marcar para limpiar después de un tiempo
    if error or complete or current >= total:
        threading.Timer(5.0, cleanup_task, args=[task_id]).start()

def cleanup_task(task_id):
    """Elimina la tarea después de un tiempo para liberar memoria"""
    if task_id in tasks_progress:
        del tasks_progress[task_id]

# Asegurarse de que exista la carpeta de subidas
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/progress/<task_id>')
def progress(task_id):
    return Response(
        event_stream(task_id),
        mimetype='text/event-stream'
    )

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No se ha seleccionado ningún archivo'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No se ha seleccionado ningún archivo'}), 400
    
    if file and file.filename.endswith('.srt'):
        # Crear nombre de archivo seguro
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        # Crear ruta completa para el archivo de salida en la misma ubicación que el original
        original_path = os.path.abspath(filepath)
        original_dir = os.path.dirname(original_path)
        original_name = os.path.splitext(os.path.basename(original_path))[0]
        output_filename = f"{original_name}_español.srt"
        output_path = os.path.join(original_dir, output_filename)
        
        # Obtener configuración de LM Studio
        lmstudio_url = request.form.get('lmstudio_url', 'http://localhost')
        lmstudio_port = request.form.get('lmstudio_port', '1234')
        lines_per_batch = int(request.form.get('lines_per_batch', 8))
        api_url = f"{lmstudio_url}:{lmstudio_port}/v1/chat/completions"
        
        # Guardar el archivo
        file.save(filepath)
        
        # Crear un ID de tarea único
        task_id = str(uuid.uuid4())
        tasks_progress[task_id] = {
            'current': 0,
            'total': 1,
            'progress': 0,
            'status': 'Iniciando traducción...',
            'complete': False,
            'output_filename': output_filename
        }
        
        # Iniciar el procesamiento en segundo plano
        from threading import Thread
        
        def process_task():
            try:
                # Procesar el archivo
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Dividir en lotes
                from traductor_final import dividir_subtitulos
                batches = dividir_subtitulos(content, lines_per_batch=lines_per_batch)
                
                total_batches = len(batches)
                update_progress(task_id, 0, total_batches, 'Procesando...')
                
                results = []
                for i, batch in enumerate(batches, 1):
                    # Actualizar progreso
                    update_progress(
                        task_id, 
                        i, 
                        total_batches, 
                        f'Traduciendo lote {i} de {total_batches}...'
                    )
                    
                    # Traducir el lote
                    translation = translate_batch(batch, api_url)
                    if translation and len(translation) > 10:
                        results.append(translation)
                    else:
                        results.append(batch)
                    
                    time.sleep(0.5)
                
                # Guardar el resultado
                try:
                    with open(output_path, 'w', encoding='utf-8') as f:
                        f.write('\n\n'.join(results))
                    
                    update_progress(
                        task_id, 
                        total_batches, 
                        total_batches, 
                        f'¡Traducción completada! Guardado en: {output_path}'
                    )
                except Exception as e:
                    update_progress(
                        task_id,
                        total_batches,
                        total_batches,
                        f'Error al guardar el archivo: {str(e)}'
                    )
                    raise
                
            except Exception as e:
                update_progress(
                    task_id,
                    0,
                    1,
                    f'Error: {str(e)}'
                )
        
        # Iniciar el hilo de procesamiento
        Thread(target=process_task).start()
        
        return jsonify({
            'task_id': task_id,
            'message': 'Procesamiento iniciado',
            'output_filename': output_filename
        })
    
    return jsonify({'error': 'Tipo de archivo no válido. Solo se permiten archivos .srt'}), 400

@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory(
        app.config['UPLOAD_FOLDER'],
        filename,
        as_attachment=True
    )

def translate_batch(batch, api_url):
    prompt = f"SOLO traduce este texto al español. NO expliques nada, NO agregues comentarios, solo la traducción literal:\n\n{batch}"

    payload = {
        "model": "local-model",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 1000,
        "stream": False,
        "stop": ["<think>", "</think>"]
    }
    
    try:
        response = requests.post(api_url, json=payload, timeout=180)
        response.raise_for_status()
        result = response.json()['choices'][0]['message']['content']
        return re.sub(r'<think>.*?</think>', '', result, flags=re.DOTALL).strip()
    except Exception as e:
        print(f"Error en traducción: {e}")
        return None

if __name__ == '__main__':
    import re
    import requests
    
    os.makedirs('uploads', exist_ok=True)
    app.run(debug=True, port=5000, threaded=True)
