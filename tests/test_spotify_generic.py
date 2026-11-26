"""F.R.I.D.A.Y: "play some music" resumes or shuffles Liked Songs; it never searches Spotify for the words "recently played"."""
import importlib.util, os, sys, tempfile, unittest
from unittest import mock

os.environ.setdefault('ATTICUS_DIR', tempfile.mkdtemp())
spec = importlib.util.spec_from_file_location('atticus_spg', os.path.join(os.path.dirname(__file__), '..', 'atticus.py'))
a = importlib.util.module_from_spec(spec); sys.argv = ['atticus.py']; spec.loader.exec_module(a)
MAC = {'id': 'mac', 'type': 'Computer', 'name': 'MacBook'}
SONG = {'name': 'Bad Habit', 'artists': [{'name': 'Steve Lacy'}]}


class Api:
    """A fake Spotify: records calls, answers player state."""
    def __init__(self, playing=False, item=None, resume_ok=True, item_after=SONG):
        self.calls, self.playing, self.item, self.resume_ok, self.item_after = [], playing, item, resume_ok, item_after
    def __call__(self, method, path, data=None, query=None):
        self.calls.append((method, path))
        if path == '/me/player': return {'is_playing': self.playing, 'item': self.item} if self.item else None
        if path == '/me/player/play' and data is None:
            if not self.resume_ok: raise a.SpotifyError(404, 'no context')
            self.item, self.playing = self.item_after, True
        return None


class GenericMusicTests(unittest.TestCase):
    def run_with(self, api):
        with mock.patch.object(a, 'spotify_api', api), mock.patch.object(a, 'spotify_device', return_value=MAC), \
             mock.patch.object(a, 'spotify_find', return_value=('spotify:user:me:collection', 'your Liked Songs')) as find, \
             mock.patch.object(a, 'spotify_play') as play, mock.patch.object(a.time, 'sleep'):
            return a.spotify_resume(), find, play

    def test_phrases(self):
        for words in ('music', 'some music', 'recently played', 'my recently played music', 'something', 'my music',
                      'what i was listening to', 'some good music on spotify'):
            self.assertTrue(a.GENERIC_MUSIC.fullmatch(words), words)
        for words in ('bad habit', 'music by drake', 'lofi music', 'something by taylor swift', 'unc music'):
            self.assertFalse(a.GENERIC_MUSIC.fullmatch(words), words)

    def test_resumes_where_you_left_off(self):
        out, find, play = self.run_with(Api(item=SONG))
        self.assertEqual(out, 'Picking up where you left off: Bad Habit by Steve Lacy.'); find.assert_not_called()

    def test_already_playing(self):
        out, _, _ = self.run_with(Api(playing=True, item=SONG))
        self.assertEqual(out, 'Already playing Bad Habit by Steve Lacy.')

    def test_nothing_to_resume_shuffles_liked_songs(self):
        api = Api(resume_ok=False)
        out, find, play = self.run_with(api)
        self.assertEqual(out, 'Shuffling your Liked Songs.')
        play.assert_called_once_with('spotify:user:me:collection'); self.assertIn(('PUT', '/me/player/shuffle'), api.calls)

    def test_play_never_searches_generic_words(self):
        with mock.patch.object(a, 'spotify_connected', return_value=True), mock.patch.object(a, 'spotify_resume', return_value='ok') as resume, \
             mock.patch.object(a, 'spotify_find') as find:
            self.assertEqual(a.play('recently played'), 'ok'); self.assertEqual(a.play('Some music.'), 'ok')
        find.assert_not_called(); self.assertEqual(resume.call_count, 2)

    def test_voice_command_is_instant(self):
        with mock.patch.object(a, 'spotify_connected', return_value=True), mock.patch.object(a, 'spotify_resume', return_value='ok'):
            for phrase in ('play some music', 'play music', 'put on some music please', 'can you play something'):
                self.assertEqual(a.spotify_quick(phrase), 'ok', phrase)
            self.assertNotEqual(a.spotify_quick('play unc music'), 'ok')
        self.assertTrue(a.QUICK_HINT.search('play some music'))


if __name__ == '__main__':
    unittest.main()
