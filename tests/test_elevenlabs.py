"""F.R.I.D.A.Y ElevenLabs voice: private key entry, voice choice, credits, Mac-voice fallback, credit saving. No network."""
import importlib.util, json, os, stat, sys, tempfile, unittest
from unittest import mock

os.environ.setdefault('ATTICUS_DIR', tempfile.mkdtemp())
spec = importlib.util.spec_from_file_location('atticus_eleven', os.path.join(os.path.dirname(__file__), '..', 'atticus.py'))
a = importlib.util.module_from_spec(spec); sys.argv = ['atticus.py']; spec.loader.exec_module(a)
SWIFT = open(os.path.join(os.path.dirname(__file__), '..', 'Atticus.swift')).read()
KEY = 'sk_' + 'a1' * 20
VOICES = {'voices': [{'name': 'Roger - Laid-Back', 'voice_id': 'CwhRBWXzGAHq8TQ4Fs17'}, {'name': 'Matilda', 'voice_id': 'XrExE9yKIg1WjnnlVkGX'},
                     {'name': 'Alice', 'voice_id': 'Xb7hH8MSUJpSbSDYk0k2'}, {'name': 'Friday', 'voice_id': 'AbCdEfGhIjKlMnOp1234'}]}


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.patches = [mock.patch.object(a, 'DIR', self.dir), mock.patch.object(a, 'ELEVEN', os.path.join(self.dir, 'elevenlabs.json')),
                        mock.patch.object(a, 'ELEVEN_CURL', os.path.join(self.dir, 'elevenlabs.curl'))]
        for p in self.patches: p.start()

    def tearDown(self):
        for p in self.patches: p.stop()

    def connect(self, typed=KEY, answer=VOICES, error=None):
        dialog = mock.Mock(stdout=typed + '\n')
        with mock.patch.object(a.subprocess, 'run', return_value=dialog) as run, \
             mock.patch.object(a, 'http_json', side_effect=error, return_value=answer) as http:
            a.eleven_connect()
        return run, http


class ConnectTests(Base):
    def test_key_is_private_and_a_voice_is_picked(self):
        run, http = self.connect()
        self.assertIn('with hidden answer', run.call_args_list[0][0][0][2])   # typed into a hidden macOS field, not chat
        self.assertEqual(http.call_args[1]['headers'], {'xi-api-key': KEY})
        self.assertEqual(stat.S_IMODE(os.stat(a.ELEVEN_CURL).st_mode), 0o600)
        self.assertEqual(open(a.ELEVEN_CURL).read(), f'header = "xi-api-key: {KEY}"\n')
        settings = json.load(open(a.ELEVEN, encoding='utf-8'))
        self.assertEqual(settings, {'on': True, 'voice_id': 'Xb7hH8MSUJpSbSDYk0k2', 'voice': 'Alice'})   # first favorite present
        self.assertNotIn(KEY, json.dumps(settings))
        self.assertEqual(a.eleven_key(), KEY)

    def test_bad_or_cancelled_keys_save_nothing(self):
        self.connect(typed='')   # cancelled
        self.connect(typed='not a key!')
        self.connect(error=a.SpotifyError(401, 'invalid'))
        self.connect(error=OSError('offline'))
        self.assertFalse(os.path.exists(a.ELEVEN_CURL)); self.assertFalse(os.path.exists(a.ELEVEN))


class VoiceCommandTests(Base):
    def test_before_connecting(self):
        self.assertEqual(a.quick_voice('use the elevenlabs voice'), 'ElevenLabs isn’t connected yet. Say “connect ElevenLabs” first.')
        self.assertIsNone(a.quick_voice('play some music'))
        with mock.patch.object(a.subprocess, 'Popen') as popen:
            for phrase in ('connect elevenlabs', 'okay set up eleven labs please', 'connect to 11 labs'):
                self.assertIn('Paste it there, not here', a.quick_voice(phrase), phrase)
        self.assertIn('--eleven-connect', popen.call_args[0][0])

    def test_switching_voices_and_engines(self):
        self.connect()
        with mock.patch.object(a, 'http_json', return_value=VOICES):
            self.assertEqual(a.quick_voice('use the elevenlabs voice matilda'), 'Done. This is Matilda.')
            self.assertEqual(json.load(open(a.ELEVEN, encoding='utf-8'))['voice_id'], 'XrExE9yKIg1WjnnlVkGX')
            self.assertEqual(a.quick_voice('try the friday voice'), 'Done. This is Friday.')   # a voice designed on the website
            self.assertIn('no ElevenLabs voice called Bob', a.quick_voice('use the voice bob'))
            self.assertEqual(a.quick_voice('what elevenlabs voices do you have'), 'Voices you can pick: Roger, Matilda, Alice, Friday.')
        self.assertEqual(a.quick_voice('switch to the mac voice'), 'Back to the Mac voice.')
        self.assertFalse(json.load(open(a.ELEVEN, encoding='utf-8'))['on'])
        self.assertEqual(a.quick_voice('use elevenlabs'), 'Switched to ElevenLabs, as Friday.')

    def test_credits_and_long_readings(self):
        self.connect()
        with mock.patch.object(a, 'http_json', return_value={'character_count': 2500, 'character_limit': 10000}):
            self.assertEqual(a.quick_voice('how many credits are left'), '7,500 of 10,000 credits left this month.')
        self.assertIn('uses credits faster', a.quick_voice('read briefings with elevenlabs too'))
        self.assertTrue(json.load(open(a.ELEVEN, encoding='utf-8'))['long'])
        self.assertIn('to save credits', a.quick_voice('save my credits'))
        self.assertTrue(a.QUICK_HINT.search('use the elevenlabs voice matilda'))

class RecoveryTests(Base):
    def test_speech_only_key_still_connects(self):
        calls = []
        def run(cmd, **kw):
            calls.append((cmd, kw))
            if cmd[0] == 'osascript' and 'hidden answer' in cmd[2]: return mock.Mock(stdout=KEY + '\n')
            if cmd[0] == '/usr/bin/curl': return mock.Mock(stdout='200')
            return mock.Mock(stdout='')
        with mock.patch.object(a.subprocess, 'run', side_effect=run), mock.patch.object(a, 'http_json', side_effect=a.SpotifyError(401, 'missing_permissions voices_read')):
            a.eleven_connect()
        with open(a.ELEVEN) as f: self.assertEqual(json.load(f), {'on': True, 'voice_id': 'Xb7hH8MSUJpSbSDYk0k2', 'voice': 'Alice'})
        curl = next(c for c in calls if c[0][0] == '/usr/bin/curl')
        self.assertNotIn(KEY, ' '.join(curl[0])); self.assertIn(KEY, curl[1]['input'])   # the key goes in on stdin only
        self.assertIn(['say', 'Connected. I now speak as Alice.'], [c[0] for c in calls])   # the result is said aloud

    def test_not_connected_answers_and_status(self):
        for phrase in ('how many credits left', 'how many credits are left', 'what voices do you have'):
            self.assertEqual(a.quick_voice(phrase), 'ElevenLabs isn’t connected yet. Say “connect ElevenLabs” first.', phrase)
        with mock.patch.object(a.subprocess, 'run', return_value=mock.Mock(stdout='401')), mock.patch.object(a, 'http_json', side_effect=a.SpotifyError(401, 'bad')):
            with mock.patch.object(a.subprocess, 'run', side_effect=lambda cmd, **kw: mock.Mock(stdout=KEY if cmd[0] == 'osascript' and 'hidden answer' in cmd[2] else '401')):
                a.eleven_connect()
        self.assertIn('didn’t accept that key', a.quick_voice('is elevenlabs connected'))
        self.connect()
        self.assertEqual(a.quick_voice('is elevenlabs connected'), 'Yes. ElevenLabs is connected, speaking as Alice.')


class AppTests(unittest.TestCase):
    def test_speaks_through_elevenlabs_with_fallback(self):
        for piece in ('"-K", self.elevenDir + "/elevenlabs.curl"', '"model_id": "eleven_flash_v2_5"', 'api.elevenlabs.io/v1/text-to-speech/',
                      '["401", "402", "403", "429"].contains(code)', 'elevenPausedUntil = Date().addingTimeInterval(3600)',
                      'let saveCredits = elevenOn && words.count > 700', 'if elevenOn { return found(eleven["voice_id"] as? String) }'):
            self.assertIn(piece, SWIFT)
        self.assertNotIn('xi-api-key', SWIFT)   # the key never appears in the app or its process arguments


if __name__ == '__main__':
    unittest.main()
