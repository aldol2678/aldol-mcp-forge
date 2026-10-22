"""Small allowlist; active formats never rendered. No parsing external instructions."""
from pathlib import Path
MAX_FILE=10*1024*1024
TYPES={'.png':'image/png','.jpg':'image/jpeg','.jpeg':'image/jpeg','.webp':'image/webp','.mp3':'audio/mpeg','.wav':'audio/wav','.mp4':'video/mp4','.ttf':'font/ttf','.otf':'font/otf','.woff':'font/woff','.woff2':'font/woff2','.pdf':'application/pdf','.txt':'text/plain','.json':'application/json','.glb':'model/gltf-binary'}

def validate_file(name,mime,data):
    ext=Path(name).suffix.lower(); expected=TYPES.get(ext)
    if not data or len(data)>MAX_FILE:raise ValueError('파일은 1바이트 이상 10MB 이하여야 합니다.')
    if not expected:raise ValueError('지원하지 않는 파일 형식입니다. SVG·HTML·실행 파일은 업로드할 수 없습니다.')
    checks={'.png':data.startswith(b'\x89PNG\r\n\x1a\n'),'.jpg':data.startswith(b'\xff\xd8\xff'),'.jpeg':data.startswith(b'\xff\xd8\xff'),'.webp':data[:4]==b'RIFF' and data[8:12]==b'WEBP','.wav':data[:4]==b'RIFF' and data[8:12]==b'WAVE','.mp3':data.startswith(b'ID3') or data[:2] in (b'\xff\xfb',b'\xff\xf3',b'\xff\xf2'),'.mp4':data[4:8]==b'ftyp','.pdf':data.startswith(b'%PDF-'),'.glb':data.startswith(b'glTF'),'.ttf':data.startswith(b'\x00\x01\x00\x00'),'.otf':data.startswith(b'OTTO'),'.woff':data.startswith(b'wOFF'),'.woff2':data.startswith(b'wOF2')}
    if ext in ('.txt','.json'):
        try:
            s=data.decode('utf-8')
            if '\x00' in s:raise ValueError()
            if ext=='.json':
                import json
                json.loads(s)
        except (ValueError,UnicodeDecodeError):raise ValueError('올바른 UTF-8 텍스트 또는 JSON이 아닙니다.')
    elif not checks.get(ext):raise ValueError('파일 확장자와 실제 형식이 일치하지 않습니다.')
    # Android pickers may send application/octet-stream; sniffing is authoritative.
    if mime not in (expected,'application/octet-stream','',None):raise ValueError('MIME 형식이 실제 파일과 일치하지 않습니다.')
    return expected
