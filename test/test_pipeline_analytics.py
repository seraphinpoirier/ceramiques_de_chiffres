import sqlite3
import sys
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))

from generate_candidate_stats import (
    elimination_candidate_names,
    returnee_ranking,
    returnee_sankey,
)
from generate_gender_stats import calculate_gender_stats
from workbook_data import season_candidate_counts, source_return_appearances, timeline_records


class TimelineTests(unittest.TestCase):
    def test_return_source_preserves_age_and_unknown_placement(self):
        rows = [
            ('SAISON', 'NOM', 'INITIALE', 'AGE', 'PLACE', 'ORI?'),
            ('All Stars', 'A', 'Initiale', 42, '?', 'O'),
        ]
        appearance = source_return_appearances([], rows)[0]
        self.assertEqual(appearance['age'], 42)
        self.assertIsNone(appearance['place'])
        self.assertTrue(appearance['orientation'])

    def test_parses_sections_and_classifies_named_classic_seasons(self):
        rows = [
            (1, 'Saison classique', datetime(2020, 1, 1)),
            (None, None, datetime(2020, 2, 1)),
            (1, 'Choc des Héros', datetime(2021, 1, 1)),
            (None, None, datetime(2021, 2, 1)),
            (2, 'Île des Héros', datetime(2022, 1, 1)),
            (None, None, datetime(2022, 2, 1)),
            (3, 'All Stars', datetime(2023, 1, 1)),
            (None, None, datetime(2023, 2, 1)),
            (4, 'La Tribu Maudite', datetime(2024, 1, 1)),
            (None, None, datetime(2024, 2, 1)),
        ]

        seasons = timeline_records(rows)

        self.assertEqual(
            {season['name']: season['series'] for season in seasons},
            {
                'Saison classique': 'classic',
                'Choc des Héros': 'all_stars',
                'Île des Héros': 'classic',
                'All Stars': 'all_stars',
                'La Tribu Maudite': 'classic',
            },
        )
        self.assertEqual(
            [season['start_date'] for season in seasons],
            sorted(season['start_date'] for season in seasons),
        )
        self.assertEqual(seasons[0]['duration_days'], 31)
        self.assertEqual(len({season['id'] for season in seasons}), len(seasons))

    def test_rejects_dates_without_a_matching_season(self):
        with self.assertRaisesRegex(ValueError, 'end date without a season'):
            timeline_records([(None, None, datetime(2020, 1, 1))])

    def test_candidate_counts_include_marked_classic_returns_and_allstars_rows(self):
        classic_rows = [
            ('ANNEE', 'SAISON', 'NOM', 'CB?'),
            (2020, 'Saison partagée', 'A', None),
            (2020, 'Saison partagée', 'B', 'O'),
        ]
        all_stars_rows = [
            ('ANNEE', 'SAISON', 'NOM'),
            (2020, 'Saison partagée', 'C'),
        ]
        counts = season_candidate_counts(classic_rows, all_stars_rows)
        dates_rows = [
            (1, 'Saison partagée', datetime(2020, 1, 1)),
            (None, None, datetime(2020, 2, 1)),
            (2, 'Sans candidats', datetime(2021, 1, 1)),
            (None, None, datetime(2021, 2, 1)),
        ]

        seasons = timeline_records(dates_rows, counts)

        self.assertEqual(seasons[0]['candidate_count'], 3)
        self.assertEqual(
            seasons[0]['candidate_counts_by_source'],
            {'CLASSIQUES': 2, 'ALLSTARS': 1},
        )
        self.assertEqual(seasons[1]['candidate_count'], 0)

    def test_candidate_counts_reject_missing_names_and_unmatched_seasons(self):
        with self.assertRaisesRegex(ValueError, 'missing season or candidate name'):
            season_candidate_counts([('SAISON', 'NOM'), ('Saison A', None)], [])
        counts = season_candidate_counts([('SAISON', 'NOM'), ('Saison B', 'A')], [])
        dates = [(1, 'Saison A', datetime(2020, 1, 1)), (None, None, datetime(2020, 2, 1))]
        with self.assertRaisesRegex(ValueError, 'missing from DATES'):
            timeline_records(dates, counts)


class GenderStatsTests(unittest.TestCase):
    def test_outcome_totals_count_all_classic_rows_but_overall_excludes_returns(self):
        conn = sqlite3.connect(':memory:')
        self.addCleanup(conn.close)
        conn.execute('CREATE TABLE Candidats (genre TEXT)')
        conn.execute('CREATE TABLE Retours (genre TEXT, saison TEXT)')
        conn.executemany('INSERT INTO Candidats VALUES (?)', [('F',), ('H',)])
        # This linked comeback is already represented by the second source row.
        conn.execute("INSERT INTO Retours VALUES ('H', 'Saison B')")
        classic_rows = [
            ('GENRE', 'ORI?', 'POT?', 'PLACE', 'CB?'),
            ('F', 'O', 'O', 1, None),
            ('H', 'O', None, 3, 'O'),
            ('F', None, None, 1, 'O'),
        ]

        stats = calculate_gender_stats(conn, classic_rows)

        self.assertEqual(stats['overall'], {'H': 1, 'F': 1, 'total': 2})
        self.assertEqual(stats['ori'], {'H': 1, 'F': 1, 'total': 2})
        self.assertEqual(stats['pot'], {'H': 0, 'F': 1, 'total': 1})
        self.assertEqual(stats['place'], {'H': 0, 'F': 2, 'total': 2})


class CandidateAnalyticsTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(':memory:')
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript('''
            CREATE TABLE Candidats (
                id_candidat INTEGER PRIMARY KEY, nom TEXT, saison TEXT, genre TEXT,
                place INTEGER, ori INTEGER, amb INTEGER, pot INTEGER, age INTEGER
            );
            CREATE TABLE Retours (
                id_retour INTEGER PRIMARY KEY, id_candidat INTEGER, annee INTEGER,
                saison TEXT, place INTEGER, source TEXT
            );
        ''')
        self.addCleanup(self.conn.close)

    def test_elimination_groups_include_names_and_seasons(self):
        self.conn.executemany('''
            INSERT INTO Candidats (id_candidat, nom, saison, genre, place, ori, amb, pot)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', [
            (1, 'Orientation', 'Saison A', 'F', 5, 1, 0, 0),
            (2, 'Poteaux', 'Saison A', 'H', 3, 1, 0, 1),
            (3, 'Third', 'Saison B', 'H', 3, 0, 0, 0),
            (4, 'Ambassador', 'Saison B', 'F', 4, 0, 1, 0),
        ])
        groups = elimination_candidate_names(self.conn)

        self.assertEqual([row['nom'] for row in groups['orientation']], ['Orientation'])
        self.assertEqual([row['nom'] for row in groups['third']], ['Poteaux', 'Third'])
        self.assertEqual(groups['ambassadors'][0]['saison'], 'Saison B')

    def test_sankey_includes_zero_return_candidates_and_unknown_gender(self):
        self.conn.executemany(
            'INSERT INTO Candidats (id_candidat, nom, saison, genre) VALUES (?, ?, ?, ?)',
            [(1, 'A', 'S1', 'F'), (2, 'B', 'S1', 'H'), (3, 'C', 'S1', None)],
        )
        self.conn.execute(
            'INSERT INTO Retours (id_candidat, saison, source) VALUES (1, "S2", "ALLSTARS")'
        )

        sankey = returnee_sankey(self.conn)

        self.assertEqual(sankey['total_candidates'], 3)
        self.assertEqual(sankey['total_linked_returns'], 1)
        self.assertEqual(
            [(link['gender'], link['linked_returns'], link['candidates'])
             for link in sankey['links'] if link['candidates']],
            [('F', 1, 1), ('H', 0, 1), ('unknown', 0, 1)],
        )

    def test_ranking_uses_source_flags_and_includes_cutoff_ties(self):
        timeline = [
            {'name': 'Initiale', 'start_date': '2000-01-01', 'end_date': '2000-02-01'},
            {'name': 'Retour', 'start_date': '2010-01-01', 'end_date': '2010-02-01'},
        ]
        appearances = []
        for candidate_id in range(1, 12):
            name = f'Candidate {candidate_id}'
            return_place = 1 if candidate_id <= 9 else 2
            self.conn.execute('''
                INSERT INTO Candidats (id_candidat, nom, saison, genre, place, ori)
                VALUES (?, ?, 'Initiale', 'F', 2, 0)
            ''', (candidate_id, name))
            self.conn.execute('''
                INSERT INTO Retours (id_candidat, annee, saison, place, source)
                VALUES (?, 2010, 'Retour', ?, 'ALLSTARS')
            ''', (candidate_id, return_place))
            appearances.append({
                'source': 'ALLSTARS', 'season': 'Retour', 'name': name,
                'origin': 'Initiale', 'orientation': False, 'place': return_place, 'age': 35,
            })

        result = returnee_ranking(
            self.conn, timeline, appearances, today=datetime(2026, 1, 1)
        )

        self.assertEqual(len(result['candidates']), 11)
        ranks = {candidate['nom']: candidate['rank'] for candidate in result['candidates']}
        self.assertEqual({ranks[f'Candidate {i}'] for i in range(1, 10)}, {1})
        self.assertEqual({ranks['Candidate 10'], ranks['Candidate 11']}, {10})
        self.assertEqual(result['candidates'][0]['orientation_access_rate'], 0)
        self.assertEqual(result['candidates'][0]['orientation_span_days'], None)
        self.assertEqual(result['candidates'][-1]['best_comeback_place'], 2)
        self.assertEqual(result['unmatched_linked_appearances'], 0)

    def test_ranking_applies_each_tiebreaker_in_order(self):
        timeline = [
            {'name': name, 'start_date': f'{year}-01-01', 'end_date': f'{year}-02-01'}
            for name, year in [('Initiale', 2000), ('Retour A', 2005),
                               ('Retour B', 2010), ('Retour C', 2015)]
        ]
        appearances = []
        specifications = [
            ('Victoire', 1, 0, [('Retour A', False, 2)]),
            ('Ecart long', 2, 1, [('Retour A', True, 2), ('Retour C', True, 2)]),
            ('Ecart court', 2, 1, [('Retour A', True, 2), ('Retour B', True, 2)]),
            ('Moins orientations', 2, 1, [('Retour A', True, 2)]),
            ('Taux inferieur', 2, 1, [('Retour A', True, 2), ('Retour B', False, 2)]),
            ('Placement connu', 2, 0, [('Retour A', False, 5)]),
            ('Placement moins bon', 2, 0, [('Retour A', False, 8)]),
            ('Placement manquant A', 2, 0, [('Retour A', False, None)]),
            ('Placement manquant B', 2, 0, [('Retour A', False, None)]),
        ]
        for candidate_id, (name, place, ori, returns) in enumerate(specifications, 1):
            self.conn.execute(
                "INSERT INTO Candidats (id_candidat, nom, saison, genre, place, ori) VALUES (?, ?, 'Initiale', 'F', ?, ?)",
                (candidate_id, name, place, ori),
            )
            for season, reached, place in returns:
                self.conn.execute(
                    "INSERT INTO Retours (id_candidat, saison, place, source) VALUES (?, ?, ?, 'ALLSTARS')",
                    (candidate_id, season, place),
                )
                appearances.append({
                    'source': 'ALLSTARS', 'season': season, 'name': name,
                    'origin': 'Initiale', 'orientation': reached, 'place': place, 'age': 35,
                })
        result = returnee_ranking(self.conn, timeline, appearances, today=datetime(2026, 1, 1))
        self.assertEqual([row['nom'] for row in result['candidates']],
                         [spec[0] for spec in specifications])
        self.assertTrue(all(row['saison_initiale'] == 'Initiale' for row in result['candidates']))
        self.assertEqual(result['candidates'][5]['best_comeback_place'], 5)
        self.assertEqual(result['candidates'][6]['best_comeback_place'], 8)
        self.assertIsNone(result['candidates'][7]['best_comeback_place'])
        self.assertEqual(result['candidates'][7]['comeback_appearances_without_placement'], 1)
        self.assertTrue(result['candidates'][7]['best_comeback_place_tiebreak_applied'])

    def test_ranking_rejects_missing_source_rows_and_dates(self):
        self.conn.execute("INSERT INTO Candidats (id_candidat, nom, saison, genre, ori) VALUES (1, 'A', 'Initiale', 'F', 1)")
        self.conn.execute("INSERT INTO Retours (id_candidat, saison, source) VALUES (1, 'Retour', 'ALLSTARS')")
        timeline = [{'name': 'Initiale', 'start_date': '2000-01-01', 'end_date': '2000-02-01'}]
        with self.assertRaisesRegex(ValueError, 'no source row'):
            returnee_ranking(self.conn, timeline, [], today=datetime(2026, 1, 1))
        appearances = [{'source': 'ALLSTARS', 'season': 'Retour', 'name': 'A',
                        'origin': 'Initiale', 'orientation': False, 'place': 2, 'age': 35}]
        with self.assertRaisesRegex(ValueError, 'Missing DATES entry'):
            returnee_ranking(self.conn, timeline, appearances, today=datetime(2026, 1, 1))

    def test_in_progress_season_counts_recorded_results_and_preserves_appearances(self):
        timeline = [
            {'name': 'Initiale', 'start_date': '2000-01-01', 'end_date': '2000-02-01'},
            {'name': 'All Stars', 'start_date': '2026-08-25', 'end_date': '2026-11-17'},
        ]
        appearances = []
        for candidate_id, name, place, orientation in [
            (1, 'Éliminée', 10, False), (2, 'En jeu', None, False),
            (3, 'Orientation', None, True),
        ]:
            self.conn.execute(
                "INSERT INTO Candidats (id_candidat, nom, saison, genre, place, ori, age) VALUES (?, ?, 'Initiale', 'F', 2, 0, 25)",
                (candidate_id, name),
            )
            self.conn.execute(
                "INSERT INTO Retours (id_candidat, saison, place, source) VALUES (?, 'All Stars', ?, 'ALLSTARS')",
                (candidate_id, place),
            )
            appearances.append({
                'source': 'ALLSTARS', 'season': 'All Stars', 'name': name,
                'origin': 'Initiale', 'orientation': orientation, 'place': place, 'age': 40,
            })

        result = returnee_ranking(self.conn, timeline, appearances, today=datetime(2026, 11, 16))
        ranked = {row['nom']: row for row in result['candidates']}
        self.assertEqual(ranked['Éliminée']['eligible_appearances'], 2)
        self.assertEqual(ranked['En jeu']['eligible_appearances'], 1)
        self.assertEqual(ranked['Orientation']['eligible_appearances'], 2)
        self.assertEqual(ranked['Éliminée']['appearances'], [
            {'season': 'Initiale', 'age': 25, 'place': 2},
            {'season': 'All Stars', 'age': 40, 'place': 10},
        ])
        self.assertIsNone(ranked['En jeu']['appearances'][1]['place'])


if __name__ == '__main__':
    unittest.main()
