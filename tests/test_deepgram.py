"""F.R.I.D.A.Y Deepgram voice: private key entry, voice choice by name, credit left, one engine at a time, app wiring. No network."""
import importlib.util, json, os, stat, sys, tempfile, unittest
from unittest import mock

os.environ.setdefault('ATTICUS_DIR', tempfile.mkdtemp())
ROOT = os.path.join(os.path.dirname(__file__), '..')
spec = importlib.util.spec_from_file_location('atticus_deepgram', os.path.join(ROOT, 'atticus.py'))
a = importlib.util.module_from_spec(spec); sys.argv = ['atticus.py']; spec.loader.exec_module(a)
SWIFT = open(os.path.join(ROOT, 'Atticus.swift')).read()
KEY = '0123456789abcdef' * 2 + '01234567'   # 40 characters, like a real Deepgram key


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.patches = [mock.patch.object(a, 'DIR', self.dir)] + [
            mock.patch.object(a, name, os.path.join(self.dir, file)) for name, file in (
                ('DEEPGRAM', 'deepgram.json'), ('DEEPGRAM_CURL', 'deepgram.curl'), ('ELEVEN', 'elevenlabs.json'),
                ('ELEVEN_CURL', 'elevenlabs.curl'), ('KOKORO', 'kokoro.json'))]
        for p in self.patches: p.start()

    def tearDown(self):
        for p in self.patches: p.stop()

    def read(self, path):
        with open(path, encoding='utf-8') as f: return json.load(f)

    def connect(self, typed=KEY, code='200'):
        calls = []
        def run(cmd, **kw):
            calls.append((cmd, kw))
            if cmd[0] == 'osascript' and 'hidden answer' in cmd[2]: return mock.Mock(stdout=typed + '\n')
            if cmd[0] == '/usr/bin/curl': return mock.Mock(stdout=code)
            return mock.Mock(stdout='')
        with mock.patch.object(a.subprocess, 'run', side_effect=run): a.deepgram_connect()
        return calls


class ConnectTests(Base):
    def test_key_is_private_checked_and_saved(self):
        a.private_json(a.ELEVEN, {'on': True, 'voice_id': 'Xb7hH8MSUJpSbSDYk0k2', 'voice': 'Alice'})
        calls = self.connect()
        self.assertIn('with hidden answer', calls[0][0][2])   # typed into a hidden macOS field, never chat
        curl = next(c for c in calls if c[0][0] == '/usr/bin/curl')
        self.assertNotIn(KEY, ' '.join(curl[0])); self.assertIn(f'Authorization: Token {KEY}', curl[1]['input'])   # stdin only
        self.assertIn('https://api.deepgram.com/v1/speak?model=aura-2-pandora-en&encoding=mp3', curl[0])
        self.assertEqual(stat.S_IMODE(os.stat(a.DEEPGRAM_CURL).st_mode), 0o600)
        self.assertEqual(open(a.DEEPGRAM_CURL).read(), f'header = "Authorization: Token {KEY}"\n')
        self.assertEqual(self.read(a.DEEPGRAM), {'on': True, 'voice': 'aura-2-pandora-en', 'name': 'Pandora'})
        self.assertFalse(self.read(a.ELEVEN)['on'])   # one cloud voice at a time
        self.assertEqual(a.deepgram_key(), KEY)
        self.assertIn(['say', 'Connected. I now speak with Deepgram, as Pandora.'], [c[0] for c in calls])   # said aloud

    def test_pasted_with_the_word_token(self):
        self.connect(typed='Token ' + KEY)
        self.assertEqual(a.deepgram_key(), KEY)

    def test_bad_cancelled_or_offline_keys_save_nothing(self):
        for typed, code, said in (('', '200', None), ('not a key!', '200', 'doesn’t look like a Deepgram key'), (KEY, '401', 'didn’t accept that key'),
                                  (KEY, '000', 'couldn’t reach Deepgram'), (KEY, '402', 'no credit left'), (KEY, '500', 'error 500')):
            calls = self.connect(typed, code)
            spoken = [c[0][1] for c in calls if c[0][0] == 'say']
            if said: self.assertIn(said, spoken[-1], (typed, code))
            else: self.assertEqual(spoken, [])
        self.assertFalse(os.path.exists(a.DEEPGRAM_CURL)); self.assertFalse(os.path.exists(a.DEEPGRAM))
        self.assertIn('error 500', a.quick_voice('is deepgram connected'))   # the last result is kept for this question


class VoiceCommandTests(Base):
    def test_before_connecting(self):
        self.assertEqual(a.quick_voice('use deepgram'), 'Deepgram isn’t connected yet. Say “connect Deepgram” first.')
        self.assertIsNone(a.quick_voice('use the pandora voice'))   # not connected: not a Deepgram request
        self.assertIsNone(a.quick_deepgram('what voices do you have'))   # Deepgram not connected: not its question
        with mock.patch.object(a.subprocess, 'Popen') as popen:
            for phrase in ('connect deepgram', 'okay set up deep gram please', 'connect to deep graham', 'friday link deepgram'):
                self.assertEqual(a.quick_voice(phrase), 'A box is opening for your Deepgram key. Paste it there, not here.', phrase)
        self.assertIn('--deepgram-connect', popen.call_args[0][0])
        for phrase in ('connect deepgram', 'use the draco voice', 'how much deepgram credit is left', 'is deepgram connected'):
            self.assertTrue(a.QUICK_HINT.search(phrase), phrase)

    def test_switching_voices_and_engines(self):
        self.connect()
        self.assertEqual(a.quick_voice('use the draco voice'), 'Done. This is Draco, a British man’s voice.')
        self.assertEqual(self.read(a.DEEPGRAM)['voice'], 'aura-2-draco-en')
        self.assertEqual(a.quick_voice('switch to the theia voice'), 'Done. This is Theia, an Australian woman’s voice.')
        self.assertEqual(a.quick_voice('try thalia on deepgram'), 'Done. This is Thalia, an American woman’s voice.')
        self.assertIn('no voice called Bob', a.quick_voice('use the deepgram voice bob'))
        listing = a.quick_voice('what voices do you have')
        self.assertIn('British woman: Pandora', listing); self.assertIn('British man: Draco', listing); self.assertIn('and more', listing)
        self.assertEqual(a.quick_voice('is deepgram connected'), 'Yes. Deepgram is connected, speaking as Thalia.')
        self.assertEqual(a.quick_voice('switch to the mac voice'), 'Back to the Mac voice.')
        self.assertFalse(self.read(a.DEEPGRAM)['on'])
        self.assertIn('another voice is on', a.quick_voice('are you using deepgram'))
        self.assertEqual(a.quick_voice('use deepgram'), 'Switched to Deepgram, as Thalia.')
        self.assertTrue(self.read(a.DEEPGRAM)['on'])

    def test_other_engines_take_over(self):
        self.connect()
        os.makedirs(os.path.join(self.dir, 'kokoro', 'venv', 'bin')); open(os.path.join(self.dir, 'kokoro', 'venv', 'bin', 'python'), 'w').close()
        self.assertEqual(a.quick_voice('use kokoro'), 'Switched to my Kokoro voice.')
        self.assertFalse(self.read(a.DEEPGRAM)['on'])
        self.assertEqual(a.quick_voice('use the pandora voice'), 'Done. This is Pandora, a British woman’s voice.')   # not "Kokoro has no voice called Pandora"
        self.assertFalse(self.read(a.KOKORO)['on']); self.assertTrue(self.read(a.DEEPGRAM)['on'])
        self.assertIsNone(a.quick_deepgram('use the voice emma'))   # a Kokoro name is not claimed by Deepgram
        with open(a.ELEVEN_CURL, 'w') as f: f.write('header = "xi-api-key: sk_x"\n')
        a.private_json(a.ELEVEN, {'on': False, 'voice_id': 'Xb7hH8MSUJpSbSDYk0k2', 'voice': 'Alice'})
        self.assertEqual(a.quick_voice('use elevenlabs'), 'Switched to ElevenLabs, as Alice.')
        self.assertFalse(self.read(a.DEEPGRAM)['on'])

    def test_credit_left(self):
        self.connect()
        def api(url, **kw):
            self.assertEqual(kw['headers'], {'Authorization': f'Token {KEY}'})
            if url.endswith('/v1/projects'): return {'projects': [{'project_id': 'p1', 'name': 'Mine'}]}
            if url.endswith('/v1/projects/p1/balances'): return {'balances': [{'balance_id': 'b', 'amount': 199.5, 'units': 'usd'}]}
            raise AssertionError(url)
        with mock.patch.object(a, 'http_json', side_effect=api):
            for phrase in ('how much credit is left', 'how many credits left', 'how much deepgram credit do i have'):
                self.assertEqual(a.quick_voice(phrase), '$199.50 of Deepgram credit left. That’s about 123 hours of talking.', phrase)
        with open(os.path.join(self.dir, 'deepgram-usage.json'), 'w') as f: json.dump({'total': 100000}, f)
        with mock.patch.object(a, 'http_json', side_effect=a.SpotifyError(403, 'insufficient permissions')):
            self.assertEqual(a.quick_voice('how much credit is left'),
                             'By my count I’ve used about $3.00 of the free $200, so roughly $197.00 is left. For the exact amount, give the key the Member role in Deepgram.')
        with mock.patch.object(a, 'http_json', side_effect=OSError('offline')):
            self.assertTrue(a.quick_voice('credits left').startswith('I couldn’t reach Deepgram. By my count'))

    def test_unrelated_words_pass_through(self):
        self.connect()
        for phrase in ('play some music', 'what is the weather', 'use the mac app', 'open control room'):
            self.assertIsNone(a.quick_deepgram(phrase), phrase)


class WiringTests(unittest.TestCase):
    def test_app_speaks_through_deepgram_and_falls_back(self):
        for piece in ('"https://api.deepgram.com/v1/speak?model=\\(deepgramVoice)&encoding=linear16&container=none&sample_rate=24000"',
                      'elevenDir + "/deepgram.curl"', '"--fail"', '"%{stderr}%{http_code}"', '"--no-buffer"',
                      'if deepgramOn { return found(deepgramVoice) }', '!kokoroOn && !deepgramOn && eleven["on"]',
                      'var studioOn: Bool { kokoroOn || deepgramOn || elevenOn', 'self.deepgramPausedUntil = Date().addingTimeInterval(3600)',
                      'if text.count > 1900 { p.finished = true; return p }', 'if p.ok { self.deepgramCount(p.text.count) }',
                      'if pieceRunning < 6 { deepgramStart(p) } else { pieceWaiting.append(p) }',
                      'if deepgramOn { return deepgramSpeak(words, fallback: fallback) }',
                      'if deepgramOn { deepgramPiece(part) } else { studioClip(part) }', '        deepgramReset()\n',
                      'if !sounded { finish(true); return fallback() }', 'guard hold.isRunning else { streamPlayer.silence(); return fallback() }',
                      'final class StreamPlayer {', 'MIT License, Copyright (c) 2025 Luke Oliff, github.com/lukeocodes/clarion',
                      'Self.voiceChunks(words)\n', 'Self.voiceChunks(spoken(partial), closedOnly: true)', '"Deepgram", "Pandora"'):
            self.assertIn(piece, SWIFT)
        self.assertNotIn('Authorization: Token', SWIFT)   # the key never appears in the app or its process arguments
        for gone in ('deepgramFetch', 'cloudFetches', 'encoding=mp3"'):
            self.assertNotIn(gone, SWIFT)   # no whole-clip Deepgram path left behind

    def test_trimming_and_holding_back(self):
        start = SWIFT.index('    static func playable(_ p: SpeechPiece) -> Data? {'); body = SWIFT[start:SWIFT.index('\n    }\n', start)]
        for piece in ('Int(0.4 * pcmRate) * 2, keep = Int(0.08 * pcmRate) * 2', 'p.first + Int(0.6 * pcmRate) * 2', 'even - Int(0.8 * pcmRate) * 2',
                      'end = min(even, j + Int(0.15 * pcmRate) * 2)', 'end &= ~1', 'let even = p.data.count & ~1'):
            self.assertIn(piece, body)

    def test_engine_order_has_no_loop(self):
        start = SWIFT.index('var deepgramOn: Bool {'); body = SWIFT[start:SWIFT.index('}', start)]
        self.assertNotIn('elevenOn', body)   # deepgramOn must not ask elevenOn, which asks deepgramOn

    def test_command_line_and_prompt(self):
        src = open(os.path.join(ROOT, 'atticus.py')).read()
        self.assertIn("if args[:1] == ['--deepgram-connect']:", src)
        self.assertIn('only via "connect ElevenLabs/Deepgram" (private box)', src)


if __name__ == '__main__':
    unittest.main()
