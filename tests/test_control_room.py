"""F.R.I.D.A.Y Control Room: its readings (--control-state), the voice command, and the window wiring in Atticus.swift."""
import importlib.util, json, os, re, subprocess, sys, tempfile, time, unittest
from unittest import mock

os.environ.setdefault('ATTICUS_DIR', tempfile.mkdtemp())
spec = importlib.util.spec_from_file_location('atticus_ctrl', os.path.join(os.path.dirname(__file__), '..', 'atticus.py'))
a = importlib.util.module_from_spec(spec); sys.argv = ['atticus.py']; spec.loader.exec_module(a)
ROOT = os.path.join(os.path.dirname(__file__), '..')
SWIFT = open(os.path.join(ROOT, 'Atticus.swift')).read()
PAGE = open(os.path.join(ROOT, 'ui', 'control.html')).read()


def fake_run(cmd, **kw):
    out = {'pmset': "Now drawing from 'AC Power'\n -InternalBattery-0 (id=1)\t87%; charging;",
           'ps': ' 50.0\n 30.0\n 20.0\n',
           'vm_stat': 'Mach Virtual Memory Statistics: (page size of 16384 bytes)\nPages active: 100000.\nPages wired down: 50000.\nPages occupied by compressor: 50000.\n',
           'sysctl': str(8 * 1024 ** 3)}[cmd[0]]
    return subprocess.CompletedProcess(cmd, 0, out, '')


class StateTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.patches = [mock.patch.object(a, 'DIR', self.dir), mock.patch.object(a, 'NEWS_DIR', os.path.join(self.dir, 'newsroom'))]
        for p in self.patches: p.start()

    def tearDown(self):
        for p in self.patches: p.stop()

    def test_system_readings(self):
        with mock.patch.object(a.subprocess, 'run', side_effect=fake_run), mock.patch.object(a.os, 'cpu_count', return_value=4):
            self.assertEqual(a.control_system(), {'battery': 87, 'cpu': 25, 'memory': 38})

    def test_cache_keeps_last_good_value(self):
        self.assertEqual(a.control_cached('x', 900, lambda: {'v': 1}), {'v': 1})
        self.assertEqual(a.control_cached('x', 0, lambda: None), {'v': 1})   # offline: the last reading stays
        self.assertEqual(a.control_cached('x', 900, lambda: {'v': 2}), {'v': 1})   # fresh enough: not fetched again

    def test_whole_state_is_json_and_survives_failures(self):
        with open(os.path.join(self.dir, 'log.jsonl'), 'w') as f:
            for i in range(6): f.write(json.dumps({'task': f'q{i}', 'reply': f'a{i}'}) + '\n')
        os.makedirs(os.path.join(self.dir, 'agents', 'x1'))
        with open(os.path.join(self.dir, 'agents', 'x1', 'context.json'), 'w') as f:
            json.dump({'title': 'Inbox triage', 'status': 'running', 'step': 'Reading mail', 'created': time.time()}, f)
        with mock.patch.object(a.subprocess, 'run', side_effect=OSError), mock.patch.object(a, 'weather_data', return_value=None), \
             mock.patch.object(a, 'spotify_connected', return_value=False), mock.patch.object(a, 'timers', return_value=[{'label': 'tea', 'ends': time.time() + 90}]):
            state = json.loads(json.dumps(a.control_state()))
        self.assertEqual(state['system'], {})
        self.assertEqual([r['you'] for r in state['transcript']], ['q0', 'q1', 'q2', 'q3', 'q4', 'q5'])
        self.assertEqual(state['agents'][0]['title'], 'Inbox triage')
        self.assertEqual(state['timers'][0]['label'], 'tea'); self.assertIn(state['timers'][0]['left'], (89, 90))
        self.assertEqual(state['music'], {'connected': False})

    def test_now_playing(self):
        now = {'is_playing': True, 'progress_ms': 1000, 'item': {'name': 'Bad Habit', 'duration_ms': 232000, 'artists': [{'name': 'Steve Lacy'}]}}
        with mock.patch.object(a, 'spotify_connected', return_value=True), mock.patch.object(a, 'spotify_api', return_value=now):
            self.assertEqual(a.control_music(), {'connected': True, 'title': 'Bad Habit', 'artist': 'Steve Lacy', 'playing': True, 'at': 1000, 'length': 232000})


class VoiceTests(unittest.TestCase):
    def test_open_phrases(self):
        for phrase in ('open the control room', 'show me the control room', 'open my hud', 'launch the command center', 'pull up the dashboard'):
            with mock.patch.object(a.subprocess, 'run') as run:
                self.assertEqual(a.quick_control(phrase), 'Opening the Control Room.', phrase)
            self.assertEqual(run.call_args[0][0], [a.APP, '--control-room'])
        self.assertIsNone(a.quick_control('what is a control room'))
        self.assertTrue(a.QUICK_HINT.search('open the control room'))


class WiringTests(unittest.TestCase):
    def test_saying_friday_does_not_open_it(self):
        start = SWIFT[SWIFT.index('    func start('):]
        self.assertNotIn('controlRoom', start[:start.index('\n    func ', 10)])

    def test_window_menu_and_launcher(self):
        self.assertIn('final class ControlRoom', SWIFT); self.assertIn('loadPage(v, "control.html")', SWIFT)
        self.assertIn('"Control Room…", #selector(openControlRoom)', SWIFT)
        self.assertIn('["--control-room"]', SWIFT); self.assertIn('py(["--control-state"])', SWIFT)

    def test_page_escapes_text_and_has_hooks(self):
        self.assertIn('window.control = {', PAGE); self.assertIn('update(s)', PAGE); self.assertIn('mode(name)', PAGE)
        self.assertIn('.scroll{flex:1;min-height:0;overflow-y:auto', PAGE); self.assertEqual(PAGE.count('stick(wasBottom)'), 2)   # transcript follows the newest line
        self.assertIn('id="wave"', PAGE); self.assertIn("wave.target = name === 'talk' ? 12 : 0", PAGE)   # the outer ring ripples only while she speaks
        self.assertIn("prefers-reduced-motion: reduce)').matches", PAGE)
        for field in ('r.you', 'r.friday', 'r.title.toUpperCase()', 'r.label.toUpperCase()'):
            self.assertIn('esc(' + field + ')', PAGE)

    def test_wake_word_stays_in_the_control_room(self):
        show = SWIFT[SWIFT.index('    func show() {'):]
        show = show[:show.index('\n    }\n')]
        self.assertIn('if controlRoom.showing && !retryOffer && askFile.isEmpty { return }', show)   # a question card still comes up
        self.assertIn('controlRoom.relay(call, arg)', SWIFT[SWIFT.index('    func js(_ call: String, _ arg: Any? = nil) {'):][:200])
        relay = SWIFT[SWIFT.index('func relay('):SWIFT.index('func windowWillClose(_ n: Notification) { rest() }')]
        for kind in ('"reset"', '"heard"', '"answer"'): self.assertIn(kind, relay)
        self.assertIn('JSONSerialization.data(withJSONObject: [kind, text])', relay)   # words reach the page as data, never as code
        self.assertIn('live(kind, text)', PAGE); self.assertIn('esc(live.heard)', PAGE); self.assertIn('esc(live.answer)', PAGE)

    def test_stays_light_on_the_mac(self):
        # spinning parts are separate layers turned by the GPU; the ripple only runs while she speaks; hidden means paused
        self.assertIn('.layer{position:absolute;inset:0;width:100%;height:100%;will-change:transform}', PAGE)
        self.assertNotIn('<g class="r1">', PAGE)
        self.assertIn('if (wave.still || document.body.classList.contains(\'paused\')) { wave.running = false; return }', PAGE)
        self.assertIn('body.paused .layer{animation-play-state:paused}', PAGE); self.assertIn('pause(on)', PAGE)
        room = SWIFT[SWIFT.index('final class ControlRoom'):SWIFT.index('let app = App()')]
        for piece in ('windowDidChangeOcclusionState', 'windowDidMiniaturize', 'p.qualityOfService = .background', 'withTimeInterval: 5,'):
            self.assertIn(piece, room)
        self.assertIn("control_cached('music', 9,", open(os.path.join(ROOT, 'atticus.py')).read())


if __name__ == '__main__':
    unittest.main()
