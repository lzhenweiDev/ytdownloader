from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import requests
import json
import os

app = Flask(__name__)
CORS(app)

# Nutze Piped API (funktioniert ohne Blockierung)
PIPED_API = "https://pipedapi.kavin.rocks"

@app.route('/')
def home():
    try:
        return send_file('index.html')
    except:
        return '<h1>Server läuft!</h1>'

@app.route('/ping')
def ping():
    return jsonify({"status": "ok", "method": "piped-api"})

@app.route('/formats', methods=['POST'])
def get_formats():
    data = request.json
    url = data.get('url', '')
    
    if not url:
        return jsonify({"error": "Keine URL"}), 400
    
    # Video-ID extrahieren
    video_id = extract_video_id(url)
    if not video_id:
        return jsonify({"error": "Ungültige YouTube-URL"}), 400
    
    try:
        # Piped API aufrufen (wird nicht von YouTube blockiert)
        response = requests.get(
            f"{PIPED_API}/streams/{video_id}",
            timeout=15
        )
        
        if response.status_code != 200:
            return jsonify({"error": "Video nicht gefunden"}), 404
        
        data = response.json()
        
        formats = []
        
        # Video-Formate
        for stream in data.get('videoStreams', []):
            formats.append({
                'id': stream.get('url', ''),
                'quality': stream.get('quality', '?'),
                'ext': 'mp4',
                'size': format_size(stream.get('contentLength', 0)),
                'type': 'video',
                'direct_url': True
            })
        
        # Audio-Formate
        for stream in data.get('audioStreams', []):
            formats.append({
                'id': stream.get('url', ''),
                'quality': stream.get('quality', 'Audio'),
                'ext': 'm4a',
                'size': format_size(stream.get('contentLength', 0)),
                'type': 'audio',
                'direct_url': True
            })
        
        return jsonify({
            'title': data.get('title', 'Unbekannt'),
            'duration': data.get('duration', 0),
            'uploader': data.get('uploader', 'Unbekannt'),
            'thumbnail': data.get('thumbnailUrl', ''),
            'formats': formats[:20]
        })
        
    except Exception as e:
        print(f"Fehler: {e}")
        return jsonify({"error": str(e)}), 400

@app.route('/download', methods=['POST'])
def download():
    data = request.json
    format_url = data.get('format_id', '')
    
    if not format_url:
        return jsonify({"error": "Keine Format-URL"}), 400
    
    try:
        # Direkt von Piped/CDN herunterladen
        response = requests.get(format_url, stream=True, timeout=60)
        
        if response.status_code != 200:
            return jsonify({"error": "Download fehlgeschlagen"}), 400
        
        # Temporär speichern
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tmp:
            for chunk in response.iter_content(chunk_size=8192):
                tmp.write(chunk)
            tmp_path = tmp.name
        
        return send_file(tmp_path, as_attachment=True, download_name='video.mp4')
        
    except Exception as e:
        return jsonify({"error": str(e)}), 400

def extract_video_id(url):
    """Extrahiert YouTube Video-ID"""
    import re
    patterns = [
        r'youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})',
        r'youtu\.be/([a-zA-Z0-9_-]{11})',
        r'youtube\.com/embed/([a-zA-Z0-9_-]{11})',
        r'youtube\.com/shorts/([a-zA-Z0-9_-]{11})'
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

def format_size(bytes_val):
    """Formatiert Bytes in lesbare Größe"""
    try:
        bytes_val = int(bytes_val)
        if bytes_val == 0:
            return '? MB'
        mb = bytes_val / (1024 * 1024)
        if mb > 1000:
            return f'{mb/1024:.1f} GB'
        return f'{mb:.1f} MB'
    except:
        return '? MB'

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8765))
    app.run(host='0.0.0.0', port=port)
