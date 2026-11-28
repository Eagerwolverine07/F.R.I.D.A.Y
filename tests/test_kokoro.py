"""F.R.I.D.A.Y's free Kokoro voice: the local helper (with a stand-in model), voice commands, and the app wiring."""
import importlib.util, io, json, os, sys, tempfile, threading, types, unittest, urllib.request
from unittest import mock

os.environ.setdefault('ATTICUS_DIR', tempfile.mkdtemp())
ROOT = os.path.join(os.path.dirname(__file__), '..')
spec = importlib.util.spec_from_file_location('atticus_kokoro', os.path.join(ROOT, 'atticus.py'))
a = importlib.util.module_from_spec(spec); sys.argv = ['atticus.py']; spec.loader.exec_module(a)
SWIFT = open(os.path.join(ROOT, 'Atticus.swift')).read()
INSTALLER = open(os.path.join(ROOT, 'Install Kokoro Voice.command')).read()


class FakeTTS:   # stands in for kokoro_mlx.KokoroTTS, which needs Apple Silicon
    loads = 0
    @classmethod
    def from_pretrained(cls, model): cls.loads += 1; return cls()
    def generate(self, text, voice='af_heart', speed=1.0):
        import numpy
        self.last = (text, voice, speed)
        return types.SimpleNamespace(audio=numpy.zeros(2400, dtype='float32'), sample_rate=24000)
    def list_voices(self): return ['af_heart', 'bf_emma']
    def close(self): pass


class HelperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.modules['kokoro_mlx'] = types.SimpleNamespace(KokoroTTS=FakeTTS)
        if 'soundfile' not in sys.modules:
            try: import soundfile  # noqa: F401
            except ImportError: raise unittest.SkipTest('soundfile not installed here')
        hs = importlib.util.spec_from_file_location('friday_kokoro', os.path.join(ROOT, 'friday_kokoro.py'))
        cls.k = importlib.util.module_from_spec(hs); hs.loader.exec_module(cls.k)
        from http.server import ThreadingHTTPServer
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), cls.k.Handler)
        cls.url = f'http://127.0.0.1:{cls.server.server_address[1]}'
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls): cls.server.shutdown()

    def post(self, path, data):
        req = urllib.request.Request(self.url + path, data=json.dumps(data).encode(), method='POST', headers={'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=5) as r: return r.status, r.headers.get('Content-Type'), r.read()
        except urllib.error.HTTPError as e: return e.code, '', e.read()

    def test_speech_is_a_wav(self):
        code, kind, body = self.post('/v1/audio/speech', {'input': 'Hello boss.', 'voice': 'bf_emma', 'speed': 9})
        self.assertEqual((code, kind), (200, 'audio/wav')); self.assertEqual(body[:4], b'RIFF')
        self.assertEqual(self.k.state['tts'].last, ('Hello boss.', 'bf_emma', 2.0))   # speed clamped
        self.assertEqual(self.post('/v1/audio/speech', {'input': '  '})[0], 400)
        self.assertEqual(self.post('/warm', {})[0], 202)

    def test_model_unloads_when_idle(self):
        self.post('/v1/audio/speech', {'input': 'Hi.'})
        self.k.state['used'] = 0
        with mock.patch.object(self.k.time, 'sleep', side_effect=[None, SystemExit]):
            with self.assertRaises(SystemExit): self.k.unload_when_idle()
        self.assertIsNone(self.k.state['tts'])

    def test_listens_on_this_mac_only(self):
        self.assertIn("ThreadingHTTPServer(('127.0.0.1', PORT)", open(os.path.join(ROOT, 'friday_kokoro.py')).read())


class CommandTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.patches = [mock.patch.object(a, 'DIR', self.dir), mock.patch.object(a, 'KOKORO', os.path.join(self.dir, 'kokoro.json')),
                        mock.patch.object(a, 'ELEVEN', os.path.join(self.dir, 'elevenlabs.json')), mock.patch.object(a, 'ELEVEN_CURL', os.path.join(self.dir, 'elevenlabs.curl'))]
        for p in self.patches: p.start()

    def tearDown(self):
        for p in self.patches: p.stop()

    def install(self):
        os.makedirs(os.path.join(self.dir, 'kokoro', 'venv', 'bin')); open(os.path.join(self.dir, 'kokoro', 'venv', 'bin', 'python'), 'w').close()

    def read(self, path):
        with open(path) as f: return json.load(f)

    def test_not_installed(self):
        self.assertIn('Install Kokoro Voice', a.quick_voice('use kokoro'))
        self.assertIsNone(a.quick_voice('use the voice emma'))   # Kokoro not on: not a Kokoro request

    def test_switch_pick_and_list(self):
        self.install()
        a.private_json(a.ELEVEN, {'on': True, 'voice_id': 'Xb7hH8MSUJpSbSDYk0k2', 'voice': 'Alice'})
        self.assertEqual(a.quick_voice('friday use cocoro please'), 'Switched to my Kokoro voice.')
        self.assertFalse(self.read(a.ELEVEN)['on'])   # one engine at a time
        self.assertEqual(a.quick_voice('use the voice emma'), 'Done. This is Emma.')
        self.assertEqual(self.read(a.KOKORO)['voice'], 'bf_emma')
        self.assertEqual(a.quick_voice('try the lily voice'), 'Done. This is Lily.')
        self.assertIn('no voice called Bob', a.quick_voice('use the kokoro voice bob'))
        self.assertIn('British: Emma, Alice, Isabella, Lily', a.quick_voice('what voices do you have'))
        self.assertEqual(a.quick_voice('switch to the mac voice'), 'Back to the Mac voice.')
        self.assertFalse(self.read(a.KOKORO)['on'])
        self.assertTrue(a.QUICK_HINT.search('use kokoro'))


class WiringTests(unittest.TestCase):
    def test_app_uses_the_helper_and_falls_back(self):
        for piece in ('"http://127.0.0.1:3901/v1/audio/speech"', 'if kokoroOn { return found(kokoroVoice) }', '"http://127.0.0.1:3901/warm"',
                      'if status == 7 { self.kokoroPausedUntil = Date().addingTimeInterval(60) }', '!kokoroOn && !deepgramOn && eleven["on"]'):
            self.assertIn(piece, SWIFT)

    def test_installer(self):
        for piece in ('--seed', '--python 3.12', 'kokoro-mlx>=0.1.4', '--test', 'launchctl bootstrap', 'friday-kokoro-log.txt',
                      'chmod 600 "$CONF/kokoro.json"', 'Run Install F.R.I.D.A.Y first'):
            self.assertIn(piece, INSTALLER)


if __name__ == '__main__':
    unittest.main()
