from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import yt_dlp
import tempfile
import os
import random

app = Flask(__name__)
CORS(app)

# Kostenlose Proxy-Liste (WebShare - 10 Proxies)
PROXIES = [
    "http://51.89.255.23:80",
    "http://51.254.102.234:3128",
    "http://20.205.61.143:80",
    "http://50.174.220.229:8080",
    "http://47.88.3.28:3128",
]

def get_random_proxy():
    """Zufälligen Proxy auswählen"""
    return random.choice(PROXIES)

@app.route('/')
def home():
    try:
        return send_file('index.html')
    except:
        return """
        <h1>YouTube Downloader</h1>
        <p>Server läuft! Bitte index.html bereitstellen.</p>
        """

@app.route('/ping')
def ping():
    return jsonify({"status": "ok", "proxies": len(PROXIES)})

@app.route('/formats', methods=['POST'])
def get_formats():
    data = request.json
    url = data.get('url', '')
    
    if not url:
        return jsonify({"error": "Keine URL"}), 400
    
    try:
        # Zufälligen Proxy nutzen
        proxy = get_random_proxy()
        print(f"🔄 Nutze Proxy: {proxy}")
        
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'skip_download': True,
            'proxy': proxy,
            'socket_timeout': 30,
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'web', 'ios'],
                }
            }
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            print(f"📥 Extrahiere: {url}")
            info = ydl.extract_info(url, download=False)
            
            formats = []
            for f in info.get('formats', []):
                if f.get('vcodec') == 'none' and f.get('acodec') == 'none':
                    continue
                
                height = f.get('height', 0) or 0
                quality = f.get('format_note', '')
                
                if not quality and height:
                    quality = f'{height}p'
                elif not quality:
                    quality = 'Audio'
                
                size = ''
                filesize = f.get('filesize') or f.get('filesize_approx')
                if filesize:
                    size_mb = filesize / 1024 / 1024
                    size = f'{size_mb:.1f} MB' if size_mb < 1000 else f'{size_mb/1024:.1f} GB'
                
                formats.append({
                    'id': f.get('format_id', ''),
                    'quality': quality,
                    'ext': f.get('ext', 'mp4'),
                    'size': size or '? MB',
                    'height': height,
                    'vcodec': f.get('vcodec', 'none'),
                    'acodec': f.get('acodec', 'none')
                })
            
            # Sortieren
            combined = [f for f in formats if f['vcodec'] != 'none' and f['acodec'] != 'none']
            video = [f for f in formats if f['vcodec'] != 'none' and f['acodec'] == 'none']
            audio = [f for f in formats if f['vcodec'] == 'none' and f['acodec'] != 'none']
            
            combined.sort(key=lambda x: x['height'], reverse=True)
            video.sort(key=lambda x: x['height'], reverse=True)
            
            all_formats = combined + video + audio
            
            print(f"✅ {len(all_formats)} Formate gefunden")
            
            return jsonify({
                'title': info.get('title', 'Unbekannt'),
                'duration': info.get('duration', 0),
                'uploader': info.get('uploader', ''),
                'thumbnail': info.get('thumbnail', ''),
                'formats': all_formats[:20]
            })
            
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Fehler: {error_msg}")
        
        # Bessere Fehlermeldungen
        if '403' in error_msg or 'Forbidden' in error_msg:
            error_msg = 'YouTube blockiert den Server. Bitte später erneut versuchen.'
        elif 'Sign in' in error_msg:
            error_msg = 'Login erforderlich. Dieses Video ist möglicherweise altersbeschränkt.'
        elif 'win32' in error_msg.lower():
            error_msg = 'Server-Fehler. Bitte erneut versuchen.'
        
        return jsonify({"error": error_msg}), 400

@app.route('/download', methods=['POST'])
def download_video():
    data = request.json
    url = data.get('url', '')
    format_id = data.get('format_id', 'best')
    
    if not url:
        return jsonify({"error": "Keine URL"}), 400
    
    try:
        proxy = get_random_proxy()
        print(f"⬇️ Downloade mit Proxy: {proxy}")
        
        with tempfile.TemporaryDirectory() as tmpdir:
            ydl_opts = {
                'format': format_id,
                'outtmpl': os.path.join(tmpdir, '%(title)s.%(ext)s'),
                'merge_output_format': 'mp4',
                'quiet': True,
                'no_warnings': True,
                'proxy': proxy,
                'socket_timeout': 60,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
                
                files = os.listdir(tmpdir)
                if files:
                    filepath = os.path.join(tmpdir, files[0])
                    print(f"✅ Download fertig: {files[0]}")
                    return send_file(
                        filepath,
                        as_attachment=True,
                        download_name=files[0]
                    )
                else:
                    return jsonify({"error": "Keine Datei erstellt"}), 500
                    
    except Exception as e:
        print(f"❌ Download-Fehler: {e}")
        return jsonify({"error": str(e)}), 400

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8765))
    app.run(host='0.0.0.0', port=port)
