from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import yt_dlp
import tempfile
import os

app = Flask(__name__)
CORS(app)

# Pfad zur cookies.txt Datei
COOKIES_FILE = 'cookies.txt'

def get_ydl_opts(extra_opts=None):
    """Basis-Optionen mit Cookies"""
    opts = {
        'quiet': True,
        'no_warnings': True,
        'cookiefile': COOKIES_FILE,
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'web'],
            }
        }
    }
    if extra_opts:
        opts.update(extra_opts)
    return opts

@app.route('/')
def home():
    return send_file('index.html')

@app.route('/ping')
def ping():
    return jsonify({
        "status": "ok",
        "cookies": os.path.exists(COOKIES_FILE)
    })

@app.route('/formats', methods=['POST'])
def get_formats():
    data = request.json
    url = data.get('url', '')
    
    if not url:
        return jsonify({"error": "Keine URL"}), 400
    
    if not os.path.exists(COOKIES_FILE):
        return jsonify({
            "error": "Cookies nicht gefunden. Bitte cookies.txt hochladen."
        }), 400
    
    try:
        ydl_opts = get_ydl_opts({'skip_download': True})
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            formats = []
            for f in info.get('formats', []):
                # Nur nützliche Formate
                if f.get('vcodec') == 'none' and f.get('acodec') == 'none':
                    continue
                
                height = f.get('height', 0) or 0
                quality = f.get('format_note', '')
                
                # Qualitäts-Label
                if not quality and height:
                    quality = f'{height}p'
                elif not quality:
                    quality = f.get('resolution', 'Audio')
                
                # Dateigröße
                size = ''
                filesize = f.get('filesize') or f.get('filesize_approx')
                if filesize:
                    size_mb = filesize / 1024 / 1024
                    if size_mb > 1000:
                        size = f'{size_mb/1024:.1f} GB'
                    else:
                        size = f'{size_mb:.1f} MB'
                
                # Container
                ext = f.get('ext', 'mp4')
                
                formats.append({
                    'id': f.get('format_id', ''),
                    'quality': quality,
                    'ext': ext,
                    'size': size or '? MB',
                    'height': height,
                    'vcodec': f.get('vcodec', 'none'),
                    'acodec': f.get('acodec', 'none')
                })
            
            # Sortieren: Video+Audio zuerst, dann nach Qualität
            combined = [f for f in formats if f['vcodec'] != 'none' and f['acodec'] != 'none']
            video_only = [f for f in formats if f['vcodec'] != 'none' and f['acodec'] == 'none']
            audio_only = [f for f in formats if f['vcodec'] == 'none' and f['acodec'] != 'none']
            
            combined.sort(key=lambda x: x['height'], reverse=True)
            video_only.sort(key=lambda x: x['height'], reverse=True)
            
            sorted_formats = combined + video_only + audio_only
            
            return jsonify({
                'title': info.get('title', 'Unbekannt'),
                'duration': info.get('duration', 0),
                'formats': sorted_formats[:20]
            })
            
    except Exception as e:
        error_msg = str(e)
        if 'Sign in to confirm' in error_msg:
            error_msg = 'YouTube verlangt Login. Bitte aktualisiere die cookies.txt Datei.'
        return jsonify({"error": error_msg}), 400

@app.route('/download', methods=['POST'])
def download_video():
    data = request.json
    url = data.get('url', '')
    format_id = data.get('format_id', 'best')
    
    if not url:
        return jsonify({"error": "Keine URL"}), 400
    
    if not os.path.exists(COOKIES_FILE):
        return jsonify({
            "error": "Cookies nicht gefunden. Bitte cookies.txt hochladen."
        }), 400
    
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            ydl_opts = get_ydl_opts({
                'format': format_id,
                'outtmpl': os.path.join(tmpdir, '%(title)s.%(ext)s'),
                'merge_output_format': 'mp4',
            })
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
                
                files = os.listdir(tmpdir)
                if files:
                    filepath = os.path.join(tmpdir, files[0])
                    return send_file(
                        filepath,
                        as_attachment=True,
                        download_name=files[0]
                    )
                else:
                    return jsonify({"error": "Download fehlgeschlagen"}), 500
                    
    except Exception as e:
        error_msg = str(e)
        if 'Sign in to confirm' in error_msg:
            error_msg = 'YouTube verlangt Login. Bitte aktualisiere die cookies.txt.'
        return jsonify({"error": error_msg}), 400

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8765))
    app.run(host='0.0.0.0', port=port)
