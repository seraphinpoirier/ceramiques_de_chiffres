import json
import sqlite3
import sys
import unittest
from collections import Counter
from pathlib import Path
from unittest.mock import patch

import openpyxl

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
from generate_candidate_stats import age_stats, elimination_stats, finale_stats, first_outs
import load_data


class CandidateStatsTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(':memory:')
        self.conn.execute('''CREATE TABLE Candidats
            (saison TEXT, tribu TEXT, nom TEXT, genre TEXT, age INTEGER,
             place INTEGER, aban INTEGER, ori INTEGER, pot INTEGER, amb INTEGER)''')
        self.addCleanup(self.conn.close)

    def insert(self, season, team, name, gender, age, place, abandoned=0):
        self.conn.execute('INSERT INTO Candidats (saison, tribu, nom, genre, age, place, aban) VALUES (?, ?, ?, ?, ?, ?, ?)',
                          (season, team, name, gender, age, place, abandoned))

    def test_selects_each_eligible_tribe_after_excluding_abandonments(self):
        self.insert('two', 'red', 'abandon', 'F', 35, 10, 1)
        self.insert('two', 'red', 'red-out', 'H', 28, 9)
        self.insert('two', 'yellow', 'yellow-out', 'F', 40, 8, None)
        for i in range(3):
            self.insert('three', str(i), f'out-{i}', 'F', 30 + i, 5)
        for i in range(4):
            self.insert('four', str(i), f'excluded-{i}', 'H', 20, 6)
        self.assertEqual({row['nom'] for row in first_outs(self.conn)},
                         {'red-out', 'yellow-out', 'out-0', 'out-1', 'out-2'})

    def test_rejects_tied_or_missing_eligible_first_out(self):
        self.insert('two', 'red', 'one', 'F', 20, 5)
        self.insert('two', 'red', 'two', 'F', 21, 5)
        self.insert('two', 'yellow', 'three', 'H', 22, 4)
        with self.assertRaises(ValueError):
            first_outs(self.conn)
        self.conn.execute("DELETE FROM Candidats WHERE nom = 'two'")
        self.conn.execute("UPDATE Candidats SET aban = 1 WHERE tribu = 'red'")
        with self.assertRaises(ValueError):
            first_outs(self.conn)

    def test_age_counts_and_averages_exclude_unknown_ages(self):
        stats = age_stats([
            {'age': 20, 'genre': 'F'}, {'age': 40, 'genre': 'F'},
            {'age': 30, 'genre': 'H'}, {'age': None, 'genre': 'H'},
        ])
        self.assertEqual(stats['all']['counts'], {20: 1, 30: 1, 40: 1})
        self.assertEqual(stats['all']['average'], 30)
        self.assertEqual(stats['F']['average'], 30)
        self.assertEqual(stats['H']['total'], 1)
        self.assertIsNone(age_stats([])['all']['average'])

    def test_finales_include_ties_and_exclude_totem_and_third_places(self):
        self.insert('mixed', 'a', 'winner', 'F', 40, 1)
        self.insert('mixed', 'b', 'runner-up', 'H', 30, 2)
        self.insert('mixed', 'a', 'third', 'H', 25, 3)
        self.insert('tie', 'a', 'first', 'F', 30, 1)
        self.insert('tie', 'b', 'second', 'H', None, 1)
        self.insert('Totem Maudit', 'a', 'excluded', 'H', 30, 1)
        self.insert('Totem Maudit', 'b', 'also excluded', 'H', 35, 1)
        finales = finale_stats(self.conn)
        self.assertEqual([f['saison'] for f in finales], ['mixed', 'tie'])
        self.assertEqual([c['place'] for c in finales[0]['candidates']], [1, 2])
        self.assertEqual([c['place'] for c in finales[1]['candidates']], [1, 1])
        self.assertIsNone(finales[1]['candidates'][1]['age'])
        self.insert('mixed', 'b', 'extra', 'F', 20, 2)
        with self.assertRaises(ValueError):
            finale_stats(self.conn)

    def test_elimination_groups_follow_flags_and_include_unknown_gender(self):
        for name, gender in [('ori', 'F'), ('poteaux', 'H'), ('third', 'H'),
                             ('amb', None), ('unmarked', 'F')]:
            self.insert('season', 'a', name, gender, 30, 4)
        self.conn.execute("UPDATE Candidats SET ori=1, pot=NULL WHERE nom='ori'")
        self.conn.execute("UPDATE Candidats SET ori=1, pot=1 WHERE nom='poteaux'")
        self.conn.execute("UPDATE Candidats SET place=3 WHERE nom='third'")
        self.conn.execute("UPDATE Candidats SET amb=1 WHERE nom='amb'")
        self.assertEqual(elimination_stats(self.conn), {
            'orientation': {'F': 1, 'H': 0, 'unknown': 0},
            'third': {'F': 0, 'H': 1, 'unknown': 0},
            'ambassadors': {'F': 0, 'H': 0, 'unknown': 1},
        })

    def test_generated_data_matches_database(self):
        with sqlite3.connect(ROOT / 'Donnees_KL.db') as conn:
            conn.row_factory = sqlite3.Row
            expected_first_outs = [dict(row) for row in first_outs(conn)]
            expected_all = age_stats(conn.execute('SELECT age, genre FROM Candidats').fetchall())
            expected_orientation = age_stats(conn.execute(
                'SELECT age, genre FROM Candidats WHERE ori = 1').fetchall())
            expected_details = {
                'all': [dict(row) for row in conn.execute(
                    'SELECT nom, saison, place, genre, age FROM Candidats WHERE age IS NOT NULL ORDER BY saison, nom')],
                'orientation': [dict(row) for row in conn.execute(
                    'SELECT nom, saison, place, genre, age FROM Candidats WHERE age IS NOT NULL AND ori = 1 ORDER BY saison, nom')],
            }
            expected_finales = finale_stats(conn)
            expected_eliminations = elimination_stats(conn)
        with (ROOT / 'candidate_stats.json').open(encoding='utf-8') as f:
            actual = json.load(f)
        self.assertEqual(actual['first_outs']['candidates'], expected_first_outs)
        # JSON object keys are strings, unlike Counter's integer age keys.
        self.assertEqual(actual['ages'], json.loads(json.dumps({
            'all': expected_all, 'orientation': expected_orientation,
        })))
        self.assertEqual(sum(actual['first_outs']['gender'].values()), len(expected_first_outs))
        self.assertEqual(actual['first_outs']['ages'],
                         json.loads(json.dumps(age_stats(expected_first_outs))))
        self.assertEqual(actual['age_candidates'], expected_details)
        self.assertEqual(actual['finales'], expected_finales)
        self.assertEqual(actual['eliminations'], expected_eliminations)

    def test_import_excludes_only_marked_comeback_appearances(self):
        workbook = ROOT / 'data' / 'donnees_kohlanta.xlsx'
        with patch.object(load_data, 'XLSX_CANDIDATES', workbook):
            imported = load_data.load_candidates_data()
        rows = list(openpyxl.load_workbook(workbook, read_only=True, data_only=True).active.values)
        headers = list(rows[0])
        season, name, comeback = (headers.index(column) for column in ('SAISON', 'NOM', 'CB?'))
        expected = Counter((row[season], row[name]) for row in rows[1:]
                           if str(row[comeback] or '').strip().upper() != 'O')
        excluded = [(row[season], row[name]) for row in rows[1:]
                    if str(row[comeback] or '').strip().upper() == 'O']
        self.assertEqual(Counter((row['saison'], row['nom']) for row in imported), expected)
        with sqlite3.connect(ROOT / 'Donnees_KL.db') as conn:
            actual = Counter(conn.execute('SELECT saison, nom FROM Candidats').fetchall())
            self.assertEqual(actual, expected)
            for record in excluded:
                self.assertEqual(actual[record], expected[record])


if __name__ == '__main__':
    unittest.main()
