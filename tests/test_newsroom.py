"""F.R.I.D.A.Y Newsroom: feed parsing, freshness, dedup, voice commands, rules, checks. No network: get() is replaced."""
import importlib.util, json, os, sys, tempfile, time, unittest
from email.utils import formatdate
from unittest import mock

os.environ.setdefault('ATTICUS_DIR', tempfile.mkdtemp())
spec = importlib.util.spec_from_file_location('atticus_news', os.path.join(os.path.dirname(__file__), '..', 'atticus.py'))
a = importlib.util.module_from_spec(spec); sys.argv = ['atticus.py']; spec.loader.exec_module(a)
NOW = 1795000000.0


def rss(*items):
    body = ''.join(f'<item><title>{t}</title><link>https://x.test/{i}</link><description>{d}</description>'
                   + (f'<pubDate>{formatdate(NOW - age * 3600)}</pubDate>' if age is not None else '') + '</item>'
                   for i, (t, d, age) in enumerate(items))
    return f'<?xml version="1.0" encoding="UTF-8"?><rss xmlns:ht="https://trends.google.com/trending/rss"><channel>{body}</channel></rss>'


class FeedTests(unittest.TestCase):
    def test_keeps_fresh_dated_items_newest_first(self):
        xml = rss(('Old story', 'x', 40), ('Fresh story', '<b>Bold</b> &amp; summary', 2), ('Newest', 'y', 0.5), ('No date', 'z', None))
        with mock.patch.object(a, 'get', return_value=xml):
            rows = a.feed_items('BBC', 'u', now=NOW)
        self.assertEqual([r['title'] for r in rows], ['Newest', 'Fresh story'])
        self.assertEqual(rows[1]['summary'], 'Bold & summary')

    def test_google_news_keeps_real_outlet(self):
        with mock.patch.object(a, 'get', return_value=rss(('Ceasefire talks resume - Reuters', 'x', 1))):
            row = a.feed_items('Google News', 'u', now=NOW)[0]
        self.assertEqual((row['title'], row['source']), ('Ceasefire talks resume', 'Reuters'))

    def test_broken_feed_is_empty_not_a_crash(self):
        for bad in ('<html>not xml', OSError('down')):
            with mock.patch.object(a, 'get', side_effect=[bad] if isinstance(bad, Exception) else None, return_value=bad):
                self.assertEqual(a.feed_items('BBC', 'u', now=NOW), [])

    def test_trends_use_their_headlines(self):
        xml = ('<?xml version="1.0"?><rss xmlns:ht="https://trends.google.com/trending/rss"><channel><item><title>eclipse</title>'
               f'<pubDate>{formatdate(NOW - 3600)}</pubDate><ht:approx_traffic>500K+</ht:approx_traffic>'
               '<ht:news_item><ht:news_item_title>Eclipse visible tonight</ht:news_item_title></ht:news_item></item></channel></rss>')
        with mock.patch.object(a, 'get', return_value=xml):
            row = a.feed_items('Google Trends', 'u', now=NOW)[0]
        self.assertEqual(row['summary'], '500K+ searches. Eclipse visible tonight')


class GatherTests(unittest.TestCase):
    def test_dedupes_same_story_and_reports_failures(self):
        def fake(source, url, hours=0, now=None):
            if source == 'BBC': return [{'source': 'BBC', 'title': 'Senate passes major budget bill after long debate', 'summary': '', 'link': 'l', 'published': NOW - 10}]
            if source == 'NPR': return [{'source': 'NPR', 'title': 'Senate passes major budget bill after a long debate', 'summary': '', 'link': 'l', 'published': NOW - 5}]
            return []
        with mock.patch.object(a, 'feed_items', side_effect=fake), mock.patch.object(a, 'news_quote', return_value=None):
            g = a.news_gather(NOW)
        self.assertEqual(len(g['sections']['world']), 1)
        self.assertIn('CNBC', g['failed']); self.assertNotIn('BBC', g['failed'])
        self.assertEqual(g['quotes'], [])

    def test_quote_math(self):
        data = {'chart': {'result': [{'meta': {'regularMarketPrice': 101.0, 'chartPreviousClose': 90, 'regularMarketTime': 1},
                                      'indicators': {'quote': [{'close': [99.0, 100.0, 101.0]}]}}]}}
        with mock.patch.object(a, 'get', return_value=json.dumps(data)):
            q = a.news_quote('S&P 500', '^GSPC')
        self.assertEqual((q['price'], q['change_pct']), (101.0, 1.0))   # vs yesterday's close, not 5 days ago
        with mock.patch.object(a, 'get', side_effect=OSError):
            self.assertIsNone(a.news_quote('S&P 500', '^GSPC'))


class CheckTests(unittest.TestCase):
    g = {'quotes': [{'name': 'S&P 500'}]}

    def test_good_script_passes(self):
        script = 'Good morning. The S&P 500 rose. ' + 'BBC reports a calm day in the world. ' * 50
        self.assertEqual(a.news_check(script, [{}] * 8, self.g), [])

    def test_catches_lists_links_short_and_missing_markets(self):
        problems = a.news_check('- first story https://x.test\nshort', [{}], self.g)
        self.assertTrue(any('words' in p for p in problems)); self.assertTrue(any('list' in p for p in problems))
        self.assertTrue(any('links' in p for p in problems)); self.assertTrue(any('market' in p for p in problems))


class WriteTests(unittest.TestCase):
    def test_uses_only_listed_ids_and_rejects_empty(self):
        g = {'sections': {'world': [{'source': 'BBC', 'title': 'A', 'summary': '', 'link': 'l1', 'published': NOW}],
                          'markets': [{'source': 'CNBC', 'title': 'B', 'summary': '', 'link': 'l2', 'published': NOW}], 'trending': []},
             'quotes': [], 'failed': []}
        script = 'Good morning. ' + 'word ' * 120

        class P:
            def __init__(self, text): self.text = text
            def communicate(self, payload, timeout): return json.dumps({'type': 'result', 'result': self.text}), ''
        with mock.patch.object(a, 'meeting_process', return_value=P(json.dumps({'script': script, 'used': [2, 99]}))), mock.patch.object(a, 'stop_claude'):
            out, used = a.news_write(g, now=NOW)
        self.assertEqual([u['link'] for u in used], ['l2'])
        with mock.patch.object(a, 'meeting_process', return_value=P('{"script": "too short", "used": []}')), mock.patch.object(a, 'stop_claude'):
            with self.assertRaises(RuntimeError): a.news_write(g, now=NOW)

    def test_prompt_forbids_memory_facts(self):
        self.assertIn('never add facts', a.NEWS_SYSTEM); self.assertIn('untrusted', a.NEWS_SYSTEM)


class VoiceTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(); self.patch = mock.patch.object(a, 'NEWS_DIR', self.dir); self.patch.start()

    def tearDown(self): self.patch.stop()

    def test_run_phrases(self):
        for phrase in ('brief me', 'run newsroom', "what's happening in the world", 'give me the news', 'news briefing',
                       'read me my morning briefing', 'catch me up on the news', 'headlines'):
            with mock.patch.object(a.subprocess, 'Popen') as popen:
                self.assertIn('briefing together', a.quick_news(phrase), phrase)
                self.assertIn('--newsroom', popen.call_args[0][0])

    def test_unrelated_phrases_pass_through(self):
        for phrase in ('play unc music', 'what is the weather', 'news about apple stock price today in detail please'):
            self.assertIsNone(a.quick_news(phrase), phrase)

    def test_schedule_times(self):
        with mock.patch.object(a, 'news_schedule', return_value=True) as sched:
            self.assertIn('every day', a.quick_news('brief me at 9 am'))
            self.assertEqual(sched.call_args[0], (9, 0))
            a.quick_news('schedule my briefing at 7:30 pm every day'); self.assertEqual(sched.call_args[0], (19, 30))

    def test_rules_are_saved_and_listed(self):
        self.assertIn('From now on', a.quick_news('for my briefing, skip sports'))
        a.quick_news('tell newsroom to always mention India')
        self.assertEqual(a.news_rules(), ['skip sports', 'always mention India'])
        self.assertIn('skip sports', a.quick_news('what are my briefing rules'))
        a.quick_news('clear my briefing rules'); self.assertEqual(a.news_rules(), [])

    def test_show_without_briefing(self):
        self.assertIn('no briefing yet', a.quick_news('show my briefing'))

    def test_quick_hint_waits_for_news_phrases(self):
        self.assertTrue(a.QUICK_HINT.search('brief me'))


if __name__ == '__main__':
    unittest.main()
