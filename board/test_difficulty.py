import unittest
from difficulty import LEVELS
from engine import Engine

class DifficultyTests(unittest.TestCase):
    def test_each_level_sets_budget_and_switching_restores_it(self):
        engine=Engine.__new__(Engine);engine.history=[];commands=[]
        def command(text):
            commands.append(text)
            return 'D4' if text.startswith('genmove') else ''
        engine.command=command
        for visits in [*LEVELS.values(),4,4096]:
            commands.clear();engine.generate('b',seconds=1,visits=visits)
            self.assertEqual(commands,[f'kata-set-param maxVisits {visits}','kata-set-param maxTime 1','genmove b'])
    def test_invalid_budget_does_not_send_commands(self):
        engine=Engine.__new__(Engine);engine.command=lambda text:self.fail(text)
        for visits in (0,-1,1.5,True):
            with self.assertRaises(ValueError):engine.generate('b',visits=visits)
