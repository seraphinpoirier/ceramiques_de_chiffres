import json
import re
import shutil
import sqlite3
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from unittest.mock import patch

import openpyxl

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
from generate_candidate_stats import age_stats, elimination_stats, finale_stats, first_outs, returnee_stats
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
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        workbook = Path(temp_dir.name) / 'donnees_kohlanta.xlsx'
        shutil.copy2(ROOT / 'data' / 'donnees_kohlanta.xlsx', workbook)
        with patch.object(load_data, 'XLSX_CANDIDATES', workbook):
            imported = load_data.load_candidates_data()
        source = openpyxl.load_workbook(workbook, read_only=True, data_only=True)
        rows = list(source['CLASSIQUES'].values)
        source.close()
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


class ReturneeTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(':memory:')
        self.addCleanup(self.conn.close)
        self.conn.executescript('''
            CREATE TABLE Candidats (id_candidat INTEGER PRIMARY KEY, nom TEXT, saison TEXT, genre TEXT, place INTEGER);
            CREATE TABLE Retours (id_retour INTEGER PRIMARY KEY, id_candidat INTEGER, annee INTEGER,
                                  saison TEXT, place INTEGER, source TEXT);
        ''')

    def test_links_by_name_and_origin_and_reports_ambiguous_or_missing(self):
        self.conn.executemany('INSERT INTO Candidats VALUES (?, ?, ?, ?, ?)', [
            (1, 'Élodie', 'Saison A', 'F', 3),
            (2, 'Élodie', 'Saison B', 'F', 4),
            (3, 'Alex', 'Saison C', 'H', 2),
        ])
        def appearance(name, season, origin, source='ALLSTARS', gender='F'):
            return {'nom': name, 'saison': season, 'initiale': origin, 'source': source,
                    'genre': gender, 'annee': 2020, 'place': 5, 'line': 2}
        rows = [
            appearance(' elodie ', 'Retour', ' SAISON A '),
            appearance('Élodie', 'Retour', 'inconnue'),
            appearance('Élodie', 'Autre', None, 'CLASSIQUES'),
            appearance('Alex', 'Retour', 'Saison C'),
        ]
        unmatched = load_data.link_returns(self.conn, rows)
        self.assertEqual(self.conn.execute('SELECT id_candidat, saison, place FROM Retours').fetchall(),
                         [(1, 'Retour', 5)])
        self.assertEqual([reason for _, reason in unmatched],
                         ['aucune correspondance', 'correspondance ambiguë', 'genre différent'])

    def test_fifth_place_ties_and_all_placements(self):
        for gender in ('F', 'H'):
            for index, count in enumerate([4, 3, 2, 1, 1, 1, 0]):
                candidate_id = (1 if gender == 'F' else 10) + index
                self.conn.execute('INSERT INTO Candidats VALUES (?, ?, ?, ?, ?)',
                                  (candidate_id, f'{gender}{index}', 'Initiale', gender, 8))
                for year in range(count):
                    self.conn.execute('INSERT INTO Retours (id_candidat, annee, saison, place, source) VALUES (?, ?, ?, ?, ?)',
                                      (candidate_id, 2000 + year, f'Retour {year}', year + 1, 'ALLSTARS'))
        result = returnee_stats(self.conn)
        for gender in ('F', 'H'):
            self.assertEqual([candidate['retours'] for candidate in result[gender]], [4, 3, 2, 1, 1, 1])
            self.assertEqual(result[gender][0]['participations'], [
                {'saison': 'Initiale', 'place': 8, 'initiale': True},
                *[{'saison': f'Retour {i}', 'place': i + 1, 'initiale': False} for i in range(4)],
            ])

    def test_generated_returnees_match_database(self):
        with sqlite3.connect(ROOT / 'Donnees_KL.db') as conn:
            expected = returnee_stats(conn)
        with (ROOT / 'candidate_stats.json').open(encoding='utf-8') as f:
            self.assertEqual(json.load(f)['returnees'], expected)

    def test_allstars_rows_are_linked_or_reported(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            workbook = Path(temp_dir) / 'donnees_kohlanta.xlsx'
            shutil.copy2(ROOT / 'data' / 'donnees_kohlanta.xlsx', workbook)
            source = openpyxl.load_workbook(workbook, read_only=True, data_only=True)
            rows = list(source['ALLSTARS'].values)
            source.close()
        headers = {name: index for index, name in enumerate(rows[0])}
        report = (ROOT / 'candidats_non_identifies.txt').read_text(encoding='utf-8').split('CLASSIQUES :')[0]
        reported_lines = {int(line) for line in re.findall(r'^Ligne (\d+) :', report, re.MULTILINE)}
        expected = Counter(
            (load_data.normalized(row[headers['NOM']]), load_data.normalized(row[headers['INITIALE']]),
             load_data.normalized(row[headers['SAISON']]), row[headers['PLACE']])
            for line, row in enumerate(rows[1:], start=2) if line not in reported_lines
        )
        with sqlite3.connect(ROOT / 'Donnees_KL.db') as conn:
            actual = Counter(
                (load_data.normalized(name), load_data.normalized(origin), load_data.normalized(season), place)
                for name, origin, season, place in conn.execute('''
                    SELECT c.nom, c.saison, r.saison, r.place
                    FROM Retours r JOIN Candidats c ON c.id_candidat = r.id_candidat
                    WHERE r.source = 'ALLSTARS'
                ''')
            )
        self.assertEqual(actual, expected)
        for line in reported_lines:
            self.assertIn(f"Ligne {line} : {rows[line - 1][headers['NOM']]} |", report)


if __name__ == '__main__':
    unittest.main()
