"""F.R.I.D.A.Y's character, Focus and Quiet modes, and the morning hello ("Good morning, boss. … Shall we start?")."""
import importlib.util, json, os, sys, tempfile, time, unittest
from datetime import datetime
from unittest import mock

os.environ.setdefault('ATTICUS_DIR', tempfile.mkdtemp())
spec = importlib.util.spec_from_file_location('atticus_persona', os.path.join(os.path.dirname(__file__), '..', 'atticus.py'))
a = importlib.util.module_from_spec(spec); sys.argv = ['atticus.py']; spec.loader.exec_module(a)
SWIFT = open(os.path.join(os.path.dirname(__file__), '..', 'Atticus.swift')).read()


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.patches = [mock.patch.object(a, 'DIR', self.dir), mock.patch.object(a, 'MORNING', os.path.join(self.dir, 'friday-morning.json'))]
        for p in self.patches: p.start()

    def tearDown(self):
        for p in self.patches: p.stop()


class PersonaTests(Base):
    def test_character_is_in_every_prompt(self):
        prompt = a.system_prompt(a.NEVER)
        for piece in ('You are F.R.I.D.A.Y', '"boss" now and then', 'Never flatter or agree to please', 'only after a task is done',
                      'never with errors, bad news', 'Own mistakes'):
            self.assertIn(piece, prompt)
        self.assertNotIn('Focus mode:', prompt)

    def test_focus_and_quiet_modes(self):
        self.assertEqual(a.quick_style('focus mode'), 'Focus mode on. Short and plain.')
        self.assertIn('Focus mode: plain and brief', a.system_prompt(a.NEVER))
        self.assertEqual(a.quick_style('what mode are you in'), 'Focus mode.')
        self.assertEqual(a.quick_style('okay quiet mode please'), 'Quiet mode. I’ll only speak when you ask.')
        self.assertEqual(a.quick_style('back to normal'), 'Back to normal, boss.')
        self.assertEqual(a.friday_style(), {'focus': False, 'quiet': False})
        self.assertNotIn('Focus mode:', a.system_prompt(a.NEVER))
        for other in ('play some music', 'what is focus', 'normal people'):
            self.assertIsNone(a.quick_style(other), other)


class MorningTests(Base):
    def line(self, hour, events=(('Standup', 10), ('Lunch with Kyle', 12)), weather={'temp': 38, 'sky': 'OVERCAST'}, **kw):
        when = datetime(2026, 11, 27, hour, 5)
        evs = None if events is None else [(t, datetime(2026, 11, 27, h, 0)) for t, h in events]
        with mock.patch.object(a, 'control_cached', return_value=weather), mock.patch.object(a, 'morning_events', return_value=evs):
            return a.morning_line(now=when, **kw)

    def test_hello_wording(self):
        self.assertEqual(self.line(8), 'Good morning, boss. It’s 38 degrees and overcast. First up is Standup at 10 AM, then 1 more. Shall we start?')

    def test_once_a_day_and_only_in_the_morning(self):
        self.assertEqual(self.line(4), ''); self.assertEqual(self.line(13), '')
        self.assertTrue(self.line(8)); self.assertEqual(self.line(9), '')   # already said today
        self.assertTrue(self.line(15, force=True).startswith('Hello, boss.'))   # "good morning" asked for later

    def test_quiet_mode_and_no_calendar_access(self):
        a.set_style(quiet=True); self.assertEqual(self.line(8), ''); a.set_style(quiet=False)
        line = self.line(8, events=None, weather=None)
        self.assertEqual(line, 'Good morning, boss. Shall we start?')   # never claims a clear calendar it could not read
        os.remove(a.MORNING)
        self.assertIn('Your calendar looks clear.', self.line(8, events=()))

    def test_yes_starts_the_briefing_no_lets_it_go(self):
        self.assertIsNone(a.quick_morning('yes'))   # nothing was asked
        self.line(8)
        self.assertTrue(a.quick_hint('yeah sure'))   # right after the hello, a short reply waits for the instant path
        with mock.patch.object(a.subprocess, 'Popen') as popen:
            self.assertEqual(a.quick_morning("yes let's go"), 'Let’s go. Putting your briefing together.')
        self.assertIn('--newsroom', popen.call_args[0][0])
        self.assertIsNone(a.quick_morning('yes'))   # answered once
        self.assertFalse(a.quick_hint('yeah sure'))
        os.remove(a.MORNING); self.line(8)
        self.assertEqual(a.quick_morning('not now'), 'No problem, boss. I’m here when you need me.')

    def test_late_yes_is_not_an_answer(self):
        self.line(8)
        with open(a.MORNING) as f: data = json.load(f)
        data['asked'] = time.time() - 600
        with open(a.MORNING, 'w') as f: json.dump(data, f)
        self.assertIsNone(a.quick_morning('yes'))

    def test_good_morning_on_demand(self):
        with mock.patch.object(a, 'control_cached', return_value=None), mock.patch.object(a, 'morning_events', return_value=None):
            self.assertTrue(a.quick_morning('good morning friday').endswith('Shall we start?'))

    def test_app_greets_at_a_good_moment(self):
        check = SWIFT[SWIFT.index('func checkMorning()'):SWIFT.index('Timer.scheduledTimer(withTimeInterval: 30, repeats: true) { _ in checkMorning() }')]
        for gate in ('(5..<12).contains(hour)', 'callAppsOnMic().isEmpty', '!fullScreen', '!agentsUI.quiet', 'meeting.panel == nil', '< 60', 'py(["--morning"])'):
            self.assertIn(gate, check)
        greet = SWIFT[SWIFT.index('func morning(_ text: String)'):SWIFT.index('func showBriefing()')]
        self.assertIn('speak(text)', greet); self.assertIn('handsFree = true', greet)


if __name__ == '__main__':
    unittest.main()
