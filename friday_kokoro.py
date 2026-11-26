"""F.R.I.D.A.Y's local Kokoro voice: a tiny speech server on 127.0.0.1:3901, run by its own Python (~/.config/atticus/kokoro/venv).

Atticus.swift sends each sentence to POST /v1/audio/speech ({"input", "voice", "speed"}) and plays the WAV it gets back, through the
same pipeline as ElevenLabs and VoiceStudio (and falls back to the Mac voice if this server is down). POST /warm loads the model as the
user starts talking; the model is dropped after 30 idle minutes to give the memory back. Only this Mac can reach it.

  --serve    run the server (the LaunchAgent com.friday.kokoro does this)
  --test     download the model if needed, time one sentence, play it, print a short report
"""
import io, json, os, sys, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT, IDLE = 3901, 30 * 60
MODEL = 'mlx-community/Kokoro-82M-bf16'
lock, state = threading.Lock(), {'tts': None, 'used': 0.0}


def model():
    """The loaded model, loading it on first use."""
    with lock:
        if state['tts'] is None:
            from kokoro_mlx import KokoroTTS
            state['tts'] = KokoroTTS.from_pretrained(MODEL)
        state['used'] = time.time()
        return state['tts']


def wav(text, voice='af_heart', speed=1.0):
    import soundfile
    tts = model()
    with lock:
        result = tts.generate(text, voice=voice, speed=speed)
        state['used'] = time.time()
    out = io.BytesIO()
    soundfile.write(out, result.audio, result.sample_rate, format='WAV', subtype='PCM_16')
    return out.getvalue()


def unload_when_idle():
    while True:
        time.sleep(60)
        with lock:
            if state['tts'] is not None and time.time() - state['used'] > IDLE:
                try: state['tts'].close()
                except Exception: pass
                state['tts'] = None


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass

    def reply(self, code, body=b'', kind='application/json'):
        self.send_response(code); self.send_header('Content-Type', kind); self.send_header('Content-Length', str(len(body))); self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == '/health': return self.reply(200, json.dumps({'ok': True, 'loaded': state['tts'] is not None}).encode())
        if self.path == '/voices':
            try: return self.reply(200, json.dumps({'voices': model().list_voices()}).encode())
            except Exception as e: return self.reply(500, json.dumps({'error': str(e)[:200]}).encode())
        self.reply(404)

    def do_POST(self):
        size = min(int(self.headers.get('Content-Length') or 0), 100_000)
        try: data = json.loads(self.rfile.read(size) or b'{}')
        except ValueError: return self.reply(400, b'{"error": "bad json"}')
        if self.path == '/warm':
            threading.Thread(target=model, daemon=True).start(); return self.reply(202, b'{}')
        if self.path != '/v1/audio/speech': return self.reply(404)
        text = str(data.get('input') or '').strip()[:4000]
        if not text: return self.reply(400, b'{"error": "no text"}')
        try: speed = max(0.5, min(2.0, float(data.get('speed') or 1.0)))
        except (TypeError, ValueError): speed = 1.0
        try: return self.reply(200, wav(text, str(data.get('voice') or 'af_heart'), speed), 'audio/wav')
        except Exception as e: return self.reply(500, json.dumps({'error': str(e)[:200]}).encode())


def serve():
    threading.Thread(target=unload_when_idle, daemon=True).start()
    ThreadingHTTPServer(('127.0.0.1', PORT), Handler).serve_forever()   # this Mac only


def test():
    import subprocess, tempfile
    started = time.time(); model(); loaded = time.time() - started
    line = 'Good morning, boss. This is my new voice. Shall we start?'
    started = time.time(); audio = wav(line); made = time.time() - started
    path = os.path.join(tempfile.gettempdir(), 'friday-kokoro-test.wav')
    with open(path, 'wb') as f: f.write(audio)
    seconds = (len(audio) - 44) / 2 / 24000
    print(f'Model ready in {loaded:.1f} s. One sentence ({seconds:.1f} s of speech) made in {made:.2f} s.')
    subprocess.run(['afplay', path])


if __name__ == '__main__':
    if sys.argv[1:] == ['--serve']: serve()
    elif sys.argv[1:] == ['--test']: test()
    else: print(__doc__)
