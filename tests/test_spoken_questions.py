"""F.R.I.D.A.Y: question cards (choices, Allow / Retry) are read aloud when F.R.I.D.A.Y talks back, not only shown."""
import os, re, unittest

SWIFT = open(os.path.join(os.path.dirname(__file__), '..', 'Atticus.swift')).read()


class SpokenQuestionTests(unittest.TestCase):
    def test_choices_card_is_spoken(self):
        line = SWIFT[SWIFT.index('if line.hasPrefix("◇ ")'):]
        line = line[:line.index('continue')]
        self.assertIn('self.js("pick", j)', line)
        self.assertIn('self.talksBack', line); self.assertIn('self.speak(App.pickSpeech(', line)

    def test_ask_card_is_spoken(self):
        line = SWIFT[SWIFT.index('if line.hasPrefix("? ")'):]
        line = line[:line.index('continue\n')]
        self.assertIn('self.js("ask"', line); self.assertIn('self.speak(p[0])', line)

    def test_pick_speech_wording(self):
        body = SWIFT[SWIFT.index('static func pickSpeech'):]
        body = body[:body.index('var conversing')]
        self.assertIn('.prefix(6)', body); self.assertIn('"\\($0.offset + 1): \\($0.element)"', body)


if __name__ == '__main__':
    unittest.main()
