import http.server
import socketserver
import os
import json
import urllib.parse
import base64
import requests
import mimetypes
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

PORT = 8080
UPLOAD_DIR = 'bahan'
OUTPUT_DIR = 'hasil'
FONT_PATH = 'Font/ComicNeue-Bold.ttf'
KEY_FILE = 'gemini/gemini_key.txt'

# Pastikan folder ada
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

class ApiKeyManager:
    def __init__(self, key_file):
        self.key_file = key_file
        self.keys = self._read_keys()
        
    def _read_keys(self):
        try:
            with open(self.key_file, "r") as f: 
                return [l.strip() for l in f if l.strip()]
        except: return []
        
    def get_current_key(self):
        return self.keys[0] if self.keys else None
        
    def rotate_key(self):
        if self.keys: self.keys.append(self.keys.pop(0))

key_manager = ApiKeyManager(KEY_FILE)

def call_gemini_api(payload):
    models = ["gemini-3-flash", "gemini-2.5-flash"]

    for _ in range(len(key_manager.keys) or 1):
        api_key = key_manager.get_current_key()
        if not api_key:
            return {"error": "API Key tidak ditemukan di gemini_key.txt"}

        for model in models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
            try:
                print(f"DEBUG: Mengirim ke {model}...")
                res = requests.post(url, json=payload, timeout=60)

                if res.status_code == 200:
                    data = res.json()
                    candidate = data.get("candidates", [{}])[0]
                    content = candidate.get("content", {}).get("parts", [])

                    if not content:
                        return {"error": "Respon kosong dari Gemini"}

                    text = content[0].get("text", "")
                    clean = text.replace("```json", "").replace("```", "").strip()

                    try:
                        return json.loads(clean)
                    except:
                        return {"translations": [clean]}

                if res.status_code == 429:
                    print(f"⚠️ Quota habis: {model}, mencoba fallback...")
                    continue

                print(f"❌ Gemini error {res.status_code}: {res.text}")

            except Exception as e:
                print(f"❌ Request gagal {model}: {e}")

        key_manager.rotate_key()

    return {"error": "Semua model Gemini gagal dihubungi."}

def call_gemini_vision(image_path, target_lang="Indonesian"):
    # ... (kode call_gemini_vision tetap sama) ...
    mime_type, _ = mimetypes.guess_type(image_path)
    if not mime_type: mime_type = "image/jpeg"
    
    try:
        with open(image_path, "rb") as f: 
            img_b64 = base64.b64encode(f.read()).decode()
    except Exception as e:
        return {"error": f"Gagal membaca gambar: {e}"}
        
    prompt = f"Extract all text from this comic page and translate it to {target_lang}. IMPORTANT: Maintain the original sentence structure, expressions, and tone. Return JSON: {{'translations': ['text1', 'text2']}}"
    
    payload = {
        "contents": [{
            "parts": [
                {"text": prompt}, 
                {"inline_data": {"mime_type": mime_type, "data": img_b64}}
            ]
        }],
        "generationConfig": {"response_mime_type": "application/json"}
    }
    return call_gemini_api(payload)

def wrap_text_pil(text, font, max_width, draw):
    """Fungsi untuk memecah teks menjadi beberapa baris sesuai lebar kotak"""
    lines = []
    # Pecah berdasarkan newline manual dulu
    paragraphs = text.split('\n')
    for p in paragraphs:
        words = p.split()
        if not words:
            lines.append("")
            continue
        current_line = words[0]
        for word in words[1:]:
            test_line = current_line + " " + word
            bbox = draw.textbbox((0, 0), test_line, font=font)
            if (bbox[2] - bbox[0]) <= max_width:
                current_line = test_line
            else:
                lines.append(current_line)
                current_line = word
        lines.append(current_line)
    return lines

class KomikServerHandler(http.server.SimpleHTTPRequestHandler):
    def do_POST(self):
        if self.path == '/upload':
            try:
                # Dapatkan nama file dari header custom
                file_name = self.headers.get('X-File-Name', 'uploaded_image.png')
                file_name = urllib.parse.unquote(file_name)
                # Dapatkan ukuran file
                file_length = int(self.headers.get('Content-Length', 0))
                
                if file_length > 0:
                    # Baca data file
                    file_data = self.rfile.read(file_length)
                    
                    # Simpan ke folder bahan
                    filepath = os.path.join(UPLOAD_DIR, os.path.basename(file_name))
                    with open(filepath, 'wb') as f:
                        f.write(file_data)
                    
                    # Kirim respons sukses
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    response = {'status': 'success', 'message': f'File berhasil diupload ke folder bahan.', 'url': f'/{filepath}'}
                    self.wfile.write(json.dumps(response).encode('utf-8'))
                    return
            except Exception as e:
                print(f"Error handling upload: {e}")
                
            self.send_response(400)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"status": "error", "message": "Gagal mengupload file"}')
            return

        elif self.path == '/process_ocr':
            try:
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode('utf-8'))
                
                filename = data.get('filename')
                target_lang = data.get('target_lang', 'Indonesian')
                
                if not filename:
                    raise ValueError("Filename tidak ditemukan")
                    
                source_path = os.path.join(UPLOAD_DIR, os.path.basename(filename))
                if not os.path.exists(source_path):
                    raise FileNotFoundError(f"File {source_path} tidak ditemukan.")

                # Panggil Gemini API
                result = call_gemini_vision(source_path, target_lang)
                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(result).encode('utf-8'))
                return
                
            except Exception as e:
                print(f"Error OCR: {e}")
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error': str(e)}).encode('utf-8'))
                return

        elif self.path == '/export':
            try:
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode('utf-8'))
                
                source_path = os.path.join(UPLOAD_DIR, os.path.basename(data['fileName']))
                if not os.path.exists(source_path):
                    raise FileNotFoundError(f"File {source_path} tidak ditemukan.")

                # Buka gambar HD asli
                img = Image.open(source_path).convert('RGB')
                draw = ImageDraw.Draw(img)
                
                for el in data['elements']:
                    # 1. Gambar Background Box (Menutup teks asli)
                    # Parsing warna 'rgb(r, g, b)'
                    bg_color = el['bgColor'].replace('rgb(', '').replace(')', '').split(',')
                    bg_tuple = (int(bg_color[0]), int(bg_color[1]), int(bg_color[2]))
                    
                    x, y, w, h = el['x'], el['y'], el['w'], el['h']
                    draw.rectangle([x, y, x + w, y + h], fill=bg_tuple)
                    
                    # 2. Gambar Teks Custom
                    # Parsing warna teks
                    text_color = el['textColor'].replace('rgb(', '').replace(')', '').split(',')
                    text_tuple = (int(text_color[0]), int(text_color[1]), int(text_color[2]))
                    
                    try:
                        font = ImageFont.truetype(FONT_PATH, int(el['fontSize']))
                    except:
                        font = ImageFont.load_default()
                    
                    x, y, w, h = el['x'], el['y'], el['w'], el['h']
                    
                    # LOGIKA BARU: Paksa teks jadi huruf kapital dan gunakan wrap_text_pil
                    text_upper = el['text'].upper()
                    # Kurangi lebar sedikit (padding internal 10px) agar teks tidak mepet garis
                    lines = wrap_text_pil(text_upper, font, w - 10, draw)
                    
                    # Hitung total tinggi blok teks untuk pemusatan vertikal
                    line_heights = []
                    for line in lines:
                        if not line: # baris kosong
                            line_heights.append(int(el['fontSize']))
                            continue
                        bbox = draw.textbbox((0, 0), line, font=font)
                        line_heights.append(bbox[3] - bbox[1] if bbox[3] > bbox[1] else int(el['fontSize']))
                    
                    line_spacing = 4
                    total_text_height = sum(line_heights) + (max(0, len(lines) - 1)) * line_spacing
                    
                    # Mulai menggambar dari posisi Y agar teks di tengah secara vertikal
                    current_y = y + (h - total_text_height) / 2
                    
                    for i, line in enumerate(lines):
                        if not line:
                            current_y += int(el['fontSize']) + line_spacing
                            continue
                            
                        bbox = draw.textbbox((0, 0), line, font=font)
                        line_width = bbox[2] - bbox[0]
                        
                        # Hitung posisi X agar teks di tengah secara horizontal
                        current_x = x + (w - line_width) / 2
                        
                        draw.text((current_x, current_y), line, font=font, fill=text_tuple)
                        current_y += line_heights[i] + line_spacing
                
                # Simpan Hasil HD
                output_filename = "hasil_" + os.path.basename(data['fileName'])
                output_path = os.path.join(OUTPUT_DIR, output_filename)
                img.save(output_path, quality=95)
                
                # Respon Sukses
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                response = {
                    'status': 'success', 
                    'message': 'Gambar HD berhasil diproses!', 
                    'url': f'/{output_path}'
                }
                self.wfile.write(json.dumps(response).encode('utf-8'))
                return

            except Exception as e:
                print(f"Error Exporting: {e}")
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'status': 'error', 'message': str(e)}).encode('utf-8'))
                return

    def do_GET(self):
        # API Endpoint untuk mengambil daftar file di folder bahan
        if self.path == '/list-bahan':
            files = []
            if os.path.exists(UPLOAD_DIR):
                for f in os.listdir(UPLOAD_DIR):
                    if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp', '.gif')):
                        files.append(f)
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(files).encode('utf-8'))
            return
            
        # Panggil default handler untuk serve index.html, bahan/..., hasil/...
        return super().do_GET()

# Izinkan reuse address agar tidak error "Address already in use" saat direstart
socketserver.TCPServer.allow_reuse_address = True

if __name__ == '__main__':
    with socketserver.TCPServer(('', PORT), KomikServerHandler) as httpd:
        print("=" * 40)
        print(f" SERVER HD BERJALAN DI http://localhost:{PORT}")
        print("=" * 40)
        print("Tekan Ctrl+C untuk menghentikan server.")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
        print("\nServer berhenti.")