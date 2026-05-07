from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import yt_dlp
import tempfile
import os

app = Flask(__name__)
CORS(app)

def setup_cookies():
    """Cookies aus Umgebungsvariable in Datei schreiben"""
    cookies_content = os.environ.get('YOUTUBE_COOKIES', '')
    
    if cookies_content:
        with open('cookies.txt', 'w') as f:
            f.write(cookies_content)
        print("✅ Cookies aus Umgebungsvariable geladen")
        return True
    else:
        print("⚠️ Keine Cookies in Umgebungsvariable")
        return False

def get_ydl_opts(extra_opts=None):
    """yt-dlp Optionen mit Cookies"""
    opts = {
        'quiet': True,
        'no_warnings': True,
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'web'],
            }
        }
    }
    
    # Cookies nur verwenden wenn vorhanden
    if os.path.exists('cookies.txt'):
        opts['cookiefile'] = 'cookies.txt'
        print("🍪 Verwende cookies.txt")
    
    if extra_opts:
        opts.update(extra_opts)
    
    return opts

@app.route('/')
def home():
    try:
        return send_file('index.html')
    except:
        return '<h1>Server läuft!</h1><p>YouTube Downloader ist bereit.</p>'

@app.route('/ping')
def ping():
    has_cookies = os.path.exists('cookies.txt')
    env_cookies = bool(os.environ.get('YOUTUBE_COOKIES', ''))
    
    return jsonify({
        "status": "ok",
        "cookies_file": has_cookies,
        "cookies_env": env_cookies,
        "cookies_working": has_cookies or env_cookies
    })

@app.route('/formats', methods=['POST'])
def get_formats():
    # Cookies vor jedem Request neu laden
    setup_cookies()
    
    data = request.json
    url = data.get('url', '')
    
    if not url:
        return jsonify({"error": "Keine URL"}), 400
    
    if not os.path.exists('cookies.txt') and not os.environ.get('YOUTUBE_COOKIES'):
        return jsonify({
            "error": "Keine Cookies! Bitte YouTube-Cookies in Render-Umgebungsvariable speichern."
        }), 400
    
    try:
        ydl_opts = get_ydl_opts({'skip_download': True})
        
        print(f"📥 Extrahiere: {url}")
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
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
        
        if 'Sign in' in error_msg:
            error_msg = 'Cookies ungültig oder abgelaufen. Bitte neue Cookies exportieren.'
        elif '403' in error_msg:
            error_msg = 'Zugriff verweigert. Cookies möglicherweise abgelaufen.'
        
        return jsonify({"error": error_msg}), 400

@app.route('/download', methods=['POST'])
def download_video():
    setup_cookies()
    
    data = request.json
    url = data.get('url', '')
    format_id = data.get('format_id', 'best')
    
    if not url:
        return jsonify({"error": "Keine URL"}), 400
    
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            ydl_opts = get_ydl_opts({
                'format': format_id,
                'outtmpl': os.path.join(tmpdir, '%(title)s.%(ext)s'),
                'merge_output_format': 'mp4',
            })
            
            print(f"⬇️ Downloade: {url}")
            
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
        print(f"❌ Fehler: {e}")
        return jsonify({"error": str(e)}), 400

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8765))
    
    # Beim Start Cookies laden
    setup_cookies()
    
    print(f"🚀 Server startet auf Port {port}")
    app.run(host='0.0.0.0', port=port)
