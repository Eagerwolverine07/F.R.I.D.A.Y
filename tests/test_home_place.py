"""F.R.I.D.A.Y's home city: a set city beats the internet-address guess (wrong behind a VPN)."""
import importlib.util, json, os, sys, tempfile, unittest
from unittest import mock

os.environ.setdefault('ATTICUS_DIR', tempfile.mkdtemp())
spec = importlib.util.spec_from_file_location('atticus_home', os.path.join(os.path.dirname(__file__), '..', 'atticus.py'))
a = importlib.util.module_from_spec(spec); sys.argv = ['atticus.py']; spec.loader.exec_module(a)
BOSTON = {'name': 'Boston', 'admin1': 'Massachusetts', 'country_code': 'US', 'latitude': 42.36, 'longitude': -71.06, 'timezone': 'America/New_York'}
SINGAPORE = '{"city": "Singapore", "region": "Singapore", "country": "SG", "loc": "1.29,103.85", "timezone": "Asia/Singapore"}'


class HomeTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.patches = [mock.patch.object(a, 'DIR', self.dir), mock.patch.object(a, 'HOME_PLACE', os.path.join(self.dir, 'friday-home.json'))]
        for p in self.patches: p.start()

    def tearDown(self):
        for p in self.patches: p.stop()

    def test_vpn_guess_until_a_city_is_set(self):
        with mock.patch.object(a, 'get', return_value=SINGAPORE):
            self.assertEqual(a.here()['name'], 'Singapore')
            self.assertIn('Singapore, which can be wrong with a VPN', a.quick_home('where am i'))
        open(os.path.join(self.dir, 'control-weather.json'), 'w').close()
        with mock.patch.object(a, 'geocode', return_value=BOSTON):
            self.assertEqual(a.quick_home('okay friday my city is boston'), 'Got it, boss. Home is Boston, Massachusetts.')
        self.assertFalse(os.path.exists(os.path.join(self.dir, 'control-weather.json')))   # the Control Room refreshes
        with mock.patch.object(a, 'get', side_effect=AssertionError('no internet guess once a city is set')):
            self.assertEqual(a.here()['name'], 'Boston')
            self.assertEqual(a.quick_home("what's my location"), 'You’re set to Boston, Massachusetts.')
        self.assertEqual(a.quick_home('forget my city'), 'Cleared. I’ll guess from your internet connection again.')
        self.assertIsNone(a.home_place())

    def test_other_phrases(self):
        with mock.patch.object(a, 'geocode', return_value=BOSTON) as geo:
            for phrase in ('i live in boston', 'set my location to boston massachusetts', "i'm based in boston"):
                self.assertTrue(a.quick_home(phrase).startswith('Got it'), phrase)
        with mock.patch.object(a, 'geocode', return_value=None):
            self.assertIn('couldn’t find Atlantis', a.quick_home('my city is Atlantis'))
        self.assertIsNone(a.quick_home('what is the weather'))
        self.assertTrue(a.QUICK_HINT.search('my city is boston'))


if __name__ == '__main__':
    unittest.main()
