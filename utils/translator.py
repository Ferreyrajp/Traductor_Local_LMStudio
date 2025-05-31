import re
import time
import requests

def read_srt(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        return f.read()

def split_subtitles(srt_content, batch_size=8):
    blocks = re.split(r'\n\s*\n', srt_content.strip())
    return ['\n\n'.join(blocks[i:i+batch_size]) for i in range(0, len(blocks), batch_size)]

def translate_batch(batch, api_url):
    prompt = f"SOLO traduce este texto al español. NO expliques nada, NO agregues comentarios, solo la traducción:\n\n{batch}"

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
        print(f"Error: {e}")
        return None

def process_subtitle_file(input_file, output_file, api_url):
    content = read_srt(input_file)
    batches = split_subtitles(content, 8)
    results = []
    
    for i, batch in enumerate(batches, 1):
        print(f"Processing batch {i}/{len(batches)}...")
        translation = translate_batch(batch, api_url)
        if translation and len(translation) > 10:  # Verificar que no esté vacío
            results.append(translation)
        else:
            results.append(batch)
        time.sleep(0.5)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n\n'.join(results))
    
    return True
