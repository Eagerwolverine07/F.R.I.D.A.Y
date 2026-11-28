"""F.R.I.D.A.Y fillers ("On it, boss."): the agreed phrases, their grouping, file names, and the app wiring. No audio here."""
import os, re, unittest

ROOT = os.path.join(os.path.dirname(__file__), '..')
with open(os.path.join(ROOT, 'Atticus.swift'), encoding='utf-8') as f: SWIFT = f.read()
BLOCK = SWIFT[SWIFT.index('    static let fillerPhrases'):SWIFT.index('    static func fillerGroup')]
PHRASES = re.findall(r'\("(\w+)", "([^"]+)"\)', BLOCK)


def group(ask, follow_up=False):   # the same rules as App.fillerGroup
    t = ask.lower().strip()
    if follow_up: return 'chat'
    if re.search(r'\b(weather|forecast|news|headlines|search|look up|look it up|google|find out|latest|price of|stock|score|happening)\b', t): return 'lookup'
    if t.endswith('?') or re.match(r'(what|why|how|who|when|where|which|is|are|am|can|could|should|would|does|do|did|will|tell me|explain)\b', t): return 'question'
    return 'task'


def file_name(text): return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')


class PhraseTests(unittest.TestCase):
    def test_the_agreed_thirty(self):
        self.assertEqual(len(PHRASES), 30)
        counts = {g: sum(1 for p in PHRASES if p[0] == g) for g in ('task', 'question', 'lookup', 'long', 'chat', 'wit')}
        self.assertEqual(counts, {'task': 6, 'question': 6, 'lookup': 6, 'long': 4, 'chat': 5, 'wit': 3})
        self.assertIn(('task', 'On it, boss.'), PHRASES); self.assertIn(('long', 'Bear with me, boss.'), PHRASES)
        self.assertEqual(sum('boss' in p[1] for p in PHRASES), 4)   # "boss" now and then, not in every line

    def test_each_phrase_has_its_own_file(self):
        names = [file_name(p[1]) for p in PHRASES]
        self.assertEqual(len(set(names)), len(names)); self.assertIn('on-it-boss', names)
        self.assertIn('text.lowercased().replacingOccurrences(of: #"[^a-z0-9]+"#, with: "-"', SWIFT)

    def test_grouping(self):
        for ask, want in (('open spotify', 'task'), ('send the email to Kyle', 'task'), ('what time is my call tomorrow', 'question'),
                          ('why is the sky blue', 'question'), ('the meeting moved?', 'question'), ("what's the weather this week", 'lookup'),
                          ('give me the latest news', 'lookup'), ('look up the Camunda team', 'lookup')):
            self.assertEqual(group(ask), want, ask)
        self.assertEqual(group('and tomorrow?', follow_up=True), 'chat')
        for piece in (r'"\b(weather|forecast|news|headlines|search|look up|look it up|google|find out|latest|price of|stock|score|happening)\b"',
                      r'"^(what|why|how|who|when|where|which|is|are|am|can|could|should|would|does|do|did|will|tell me|explain)\b"'):
            self.assertIn(piece, SWIFT)


class WiringTests(unittest.TestCase):
    def test_when_she_says_one(self):
        for piece in ('DispatchQueue.main.asyncAfter(deadline: .now() + 0.9) { [weak self] in self?.fillerSay(group, token) }',   # not for instant answers
                      'DispatchQueue.main.asyncAfter(deadline: .now() + 7) { [weak self] in self?.fillerSay("long", token) }',
                      'guard token == fillerToken, busy, voice?.isRunning != true, !fillerPlayer.playing, let engine = fillerEngine else { return }',
                      '!fillerRecent.contains($0.text)', 'fillerRecent = Array((fillerRecent + [pick.0]).suffix(5))',
                      'guard style["focus"] as? Bool != true else { return }', 'guard talksBack, !drawing.active, let engine = fillerEngine else { return }',
                      'followUp: conversing && Date().timeIntervalSince(lastDone) < 90'):
            self.assertIn(piece, SWIFT)

    def test_hooks(self):
        self.assertIn('catch { cancel(); js("msg", "Could not confirm the request. Please try again."); return }\n            fillerArm(t)\n', SWIFT)
        self.assertIn('try "go".write(toFile: commit, atomically: true, encoding: .utf8); fillerArm(rest) }', SWIFT)
        self.assertIn('self.fillerToken += 1   // answered: no filler from here on', SWIFT)
        self.assertIn('self.fillerToken += 1; self.retryOffer = true; self.askNeed = ["pick": true];', SWIFT)
        speak = SWIFT[SWIFT.index('    func speak(_ a: String) {'):]
        self.assertTrue(speak.split('\n')[1].strip().startswith('if fillerPlayer.playing { fillerThen = { [weak self] in self?.speak(a) }; return }'))
        shush = SWIFT[SWIFT.index('    @discardableResult func shush('):]
        self.assertIn('let filler = fillerPlayer.playing; fillerHush()', shush.split('\n')[1])   # Esc and the hotkey stop it too

    def test_made_once_per_voice(self):
        for piece in ('if kokoroOn { return "kokoro-" + kokoroVoice }', 'if deepgramOn { return "deepgram-" + deepgramVoice }',
                      'if elevenOn, let id = eleven["voice_id"] as? String { return "eleven-" + id }', 'elevenDir + "/fillers/" + engine',
                      'guard !fillerMaking.contains(engine) else { return }', 'tmp = target + ".part"', '"-K", elevenDir + "/deepgram.curl"',
                      '"-K", elevenDir + "/elevenlabs.curl"', '"http://127.0.0.1:3901/v1/audio/speech"',
                      'if engine.hasPrefix("deepgram-") { self.deepgramCount(text.count) } else if mp3 { self.elevenCount(text.count) }'):
            self.assertIn(piece, SWIFT)

    def test_names_stay_clear_of_test_slices(self):
        block = SWIFT[SWIFT.index('    // F.R.I.D.A.Y fillers'):SWIFT.index('    // Characters sent this month')]
        for name in ('    func start(', '    func stop()', '    func say', '    func play('):
            self.assertNotIn(name, block)


if __name__ == '__main__':
    unittest.main()
