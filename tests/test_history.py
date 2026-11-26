"""F.R.I.D.A.Y remembers past conversations: --history understands days ("yesterday", "last Tuesday", "Nov 20") as well as words."""
import importlib.util, json, os, sys, tempfile, unittest
from datetime import datetime
from unittest import mock

os.environ.setdefault('ATTICUS_DIR', tempfile.mkdtemp())
spec = importlib.util.spec_from_file_location('atticus_hist', os.path.join(os.path.dirname(__file__), '..', 'atticus.py'))
a = importlib.util.module_from_spec(spec); sys.argv = ['atticus.py']; spec.loader.exec_module(a)
NOW = datetime(2026, 11, 26, 10, 0)   # a Thursday
ROWS = [('2026-11-17 09:00:00', 'what is the weather in Boston', '41 and clear'),
        ('2026-11-24 14:10:00', 'help me prep for the Kyle Camunda call', 'Here are five questions for Kyle'),
        ('2026-11-24 18:00:00', 'play unc music', 'Playing unc on Spotify'),
        ('2026-11-25 09:30:00', 'brief me', 'Putting your briefing together'),
        ('2026-11-25 20:00:00', 'what is a good pasta recipe', 'Try cacio e pepe'),
        ('2026-11-26 08:00:00', 'good morning', 'Good morning, boss')]


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(); self.p = mock.patch.object(a, 'DIR', self.dir); self.p.start()
        with open(os.path.join(self.dir, 'log.jsonl'), 'w') as f:
            for at, task, reply in ROWS: f.write(json.dumps({'at': at, 'task': task, 'reply': reply}) + '\n')

    def tearDown(self): self.p.stop()

    def days(self, words): return a.history_days(words, NOW)

    def test_day_words(self):
        d = lambda words: tuple(x.strftime('%m-%d') for x in self.days(words)[0])
        self.assertEqual(d('what did we talk about yesterday'), ('11-25', '11-25'))
        self.assertEqual(d('this morning'), ('11-26', '11-26'))
        self.assertEqual(d('last tuesday'), ('11-24', '11-24'))
        self.assertEqual(d('on monday'), ('11-23', '11-23'))
        self.assertEqual(d('last week'), ('11-16', '11-22'))
        self.assertEqual(d('Nov 17th'), ('11-17', '11-17'))
        self.assertEqual(d('2026-11-24'), ('11-24', '11-24'))
        self.assertEqual(d('2 days ago'), ('11-24', '11-24'))
        self.assertEqual(d('last friday'), ('11-20', '11-20'))
        self.assertIsNone(self.days('friday what did we say about pasta')[0])   # a bare "Friday" is her name, not a day
        self.assertEqual(self.days('what did we talk about yesterday')[1], [])   # only filler left: the whole day

    def test_a_whole_day_in_order(self):
        out = a.history('what did we talk about last Tuesday', NOW)
        self.assertEqual(out.count('asked:'), 2); self.assertLess(out.index('Kyle'), out.index('unc'))
        self.assertIn('Tue Nov 24, 2:10 PM', out)

    def test_words_within_a_day_and_anywhere(self):
        self.assertIn('cacio e pepe', a.history('the pasta recipe from yesterday', NOW))
        self.assertNotIn('Kyle', a.history('the pasta recipe from yesterday', NOW))
        self.assertIn('Kyle', a.history('Camunda call prep', NOW))
        self.assertEqual(a.history('what did we talk about on sunday', NOW), 'Nothing that day.')
        self.assertEqual(a.history('quantum physics', NOW), 'Nothing matches.')

    def test_ai_is_told_it_can_use_days(self):
        self.assertIn('--history', a.SYSTEM); self.assertIn('"<words, day or date>"', a.SYSTEM)


if __name__ == '__main__':
    unittest.main()
