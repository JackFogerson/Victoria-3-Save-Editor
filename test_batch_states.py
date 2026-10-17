from pathlib import Path
import tempfile
import unittest
from batch_states import load_batch, apply_batch


def fixture():
    states = ''.join(f'{i}={{\n\tregion="STATE_{i}"\n}}\n' for i in range(1, 7))
    pops = ''.join(f'{i}={{\n\tlocation={i}\n\ttype=laborers\n\tculture=1\n\treligion=protestant\n\tworkforce=100\n\tdependents=200\n}}\n' for i in range(1, 7))
    pops += '7={\n\tlocation=6\n\ttype=clerks\n\tculture=2\n\treligion=catholic\n\tworkforce=10\n}\n'
    return ('states={\n database={\n' + states + ' }\n}\npops={\n database={\n' + pops +
            ' }\n}\ncultures={\n database={\n1={\n\ttype=yankee\n\tcore_states={ STATE_1 STATE_2 STATE_3 STATE_4 STATE_5 STATE_6 }\n}\n2={\n\ttype=dixie\n}\n }\n}\nunchanged={ value=42 }\n')


class BatchTests(unittest.TestCase):
    def test_five_independent_states_one_write_and_no_backups(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as folder:
            p = Path(folder) / 'save.v3'; p.write_bytes(fixture().replace('\n', '\r\n').encode())
            snapshot = load_batch(p)
            plans = {'1': {'percentages': {'1': '20'}, 'cultures': {'1': '2'}},
                     '2': {'religions': {'protestant': 'catholic'}},
                     '3': {'percentages': {'1': '-90'}},
                     '4': {'homelands': ['2']},
                     '5': {'workforce': {'laborers': '7', 'officers': '12'}}}
            result = apply_batch(snapshot, plans)
            self.assertEqual(result['populations'], 4)
            self.assertEqual(result['skipped'], ['State 5: officers (+12)'])
            after = load_batch(p)
            self.assertEqual(after['states']['1']['cultures'], {'2': 360})
            self.assertEqual(after['states']['2']['religions'], {'catholic': 300})
            self.assertEqual(after['states']['3']['cultures'], {'1': 30})
            self.assertEqual(after['states']['4']['homelands'], ['2'])
            self.assertEqual(after['states']['5']['cultures'], {'1': 307})
            self.assertEqual(after['states']['6'], snapshot['states']['6'])
            self.assertEqual(list(Path(folder).iterdir()), [p])
            self.assertNotIn(b'\n', p.read_bytes().replace(b'\r\n', b''))
            with self.assertRaisesRegex(ValueError, 'changed'): apply_batch(snapshot, plans)

    def test_invalid_plan_and_split_conflict_leave_save_untouched(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as folder:
            p = Path(folder) / 'save.v3'; p.write_text(fixture().replace('region="STATE_2"', 'region="STATE_1"'))
            original = p.read_bytes(); snapshot = load_batch(p)
            for plans in ({'1': {'homelands': ['1']}, '2': {'homelands': ['2']}},
                          {'1': {'percentages': {'1': '-101'}}},
                          {'1': {'workforce': {'laborers': '-101'}}},
                          {'1': {'cultures': {'1': '999'}}}):
                with self.assertRaises(ValueError): apply_batch(snapshot, plans)
                self.assertEqual(p.read_bytes(), original)
            self.assertEqual(apply_batch(snapshot, {'1': {}})['records'], 0)
