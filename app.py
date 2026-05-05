from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import yt_dlp
import tempfile
import os
import re

app = Flask(__name__)
CORS(app)

@app.route('/')
def home():
    return send_file('index.html')

@app.route('/ping')
def ping():
    return jsonify({"status": "ok"})

@app.route('/formats', methods=['POST'])
def get_formats():
    data = request.json
    url = data.get('url', '')
    
    if not url:
        return jsonify({"error": "Keine URL"}), 400
    
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'skip_download': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            formats = []
            for f in info.get('formats', []):
                if f.get('vcodec') == 'none' and f.get('acodec') == 'none':
                    continue
                
                height = f.get('height', 0) or 0
                quality = f.get('format_note', 'Audio')
                
                size = ''
                if f.get('filesize'):
                    size_mb = f['filesize'] / 1024 / 1024
                    if size_mb > 1000:
                        size = f'{size_mb/1024:.1f} GB'
                    else:
                        size = f'{size_mb:.1f} MB'
                
                formats.append({
                    'id': f.get('format_id', ''),
                    'quality': quality,
                    'ext': f.get('ext', 'mp4'),
                    'size': size or 'Unbekannt'
                })
            
            # Sortieren: Beste Qualität zuerst
            formats.sort(key=lambda x: str(x['quality']), reverse=True)
            
            return jsonify({
                'title': info.get('title', 'Unbekannt'),
                'formats': formats[:15]
            })
            
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/download', methods=['POST'])
def download_video():
    data = request.json
    url = data.get('url', '')
    format_id = data.get('format_id', 'best')
    
    if not url:
        return jsonify({"error": "Keine URL"}), 400
    
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            ydl_opts = {
                'format': format_id,
                'outtmpl': os.path.join(tmpdir, '%(title)s.%(ext)s'),
                'quiet': True,
                'no_warnings': True,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
                
                files = os.listdir(tmpdir)
                if files:
                    filepath = os.path.join(tmpdir, files[0])
                    return send_file(filepath, as_attachment=True, download_name=files[0])
                else:
                    return jsonify({"error": "Download fehlgeschlagen"}), 500
                    
    except Exception as e:
        return jsonify({"error": str(e)}), 400

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8765))
    app.run(host='0.0.0.0', port=port)
