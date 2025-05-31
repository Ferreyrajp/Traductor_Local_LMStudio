import requests
import re
import time

def leer_srt(archivo):
    with open(archivo, 'r', encoding='utf-8') as f:
        return f.read()

def dividir_subtitulos(contenido_srt, lines_per_batch=8):
    """
    Divide el contenido SRT en lotes más pequeños para su procesamiento.
    
    Args:
        contenido_srt (str): Contenido del archivo SRT
        lines_per_batch (int): Número de bloques de subtítulos por lote (por defecto: 8)
        
    Returns:
        list: Lista de cadenas, cada una conteniendo múltiples bloques de subtítulos
    """
    # Divide por bloques de subtítulos (cada bloque termina con doble salto de línea)
    bloques = re.split(r'\n\s*\n', contenido_srt.strip())
    
    # Filtrar bloques vacíos
    bloques = [b for b in bloques if b.strip()]
    
    # Agrupar en lotes
    lotes = []
    for i in range(0, len(bloques), lines_per_batch):
        lote = '\n\n'.join(bloques[i:i+lines_per_batch])
        lotes.append(lote)
    
    return lotes

def traducir_lote(lote, url_api="http://localhost:1234/v1/chat/completions"):
    # Prompt ultra directo para evitar <think>
    prompt = f"SOLO traduce este texto al español. NO expliques nada, NO agregues comentarios, solo la traducción literal:\n\n{lote}"

    payload = {
        "model": "local-model",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 1000,
        "stream": False,
        "stop": ["<think>", "</think>"]  # Para el modelo si empieza a pensar
    }
    
    try:
        response = requests.post(url_api, json=payload, timeout=180)
        response.raise_for_status()
        
        resultado = response.json()['choices'][0]['message']['content']
        
        # Limpia cualquier etiqueta <think> que pueda aparecer
        resultado = re.sub(r'<think>.*?</think>', '', resultado, flags=re.DOTALL)
        resultado = resultado.strip()
        
        return resultado
        
    except Exception as e:
        print(f"Error: {e}")
        return None

def procesar_archivo_srt(archivo_entrada, archivo_salida):
    print(f"Leyendo: {archivo_entrada}")
    contenido = leer_srt(archivo_entrada)
    
    print("Dividiendo en lotes pequeños...")
    lotes = dividir_subtitulos(contenido, 8)  # Solo 8 bloques por lote
    
    print(f"Total de lotes: {len(lotes)}")
    
    resultado_completo = []
    exitosos = 0
    
    for i, lote in enumerate(lotes, 1):
        print(f"Procesando {i}/{len(lotes)}... ", end="")
        
        traduccion = traducir_lote(lote)
        
        if traduccion and len(traduccion) > 10:  # Verificar que no esté vacío
            resultado_completo.append(traduccion)
            exitosos += 1
            print("✓")
        else:
            print("✗ (usando original)")
            resultado_completo.append(lote)
        
        # Pausa corta
        time.sleep(0.5)
    
    # Guardar resultado
    with open(archivo_salida, 'w', encoding='utf-8') as f:
        f.write('\n\n'.join(resultado_completo))
    
    print(f"\n✓ Completado: {exitosos}/{len(lotes)} lotes traducidos")
    print(f"Guardado en: {archivo_salida}")

if __name__ == "__main__":
    archivo_original = "subtitulos_original.srt"
    archivo_traducido = "subtitulos_español.srt"
    
    print("=== TRADUCTOR DE SUBTÍTULOS ===")
    print("Asegúrate de que LM Studio esté corriendo")
    input("Presiona Enter para comenzar...")
    
    procesar_archivo_srt(archivo_original, archivo_traducido)