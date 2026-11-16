"""Generate candidate statistics from SQLite."""

import json
import sqlite3
import unicodedata
from collections import Counter
from datetime import date, datetime
from pathlib import Path

from workbook_data import read_workbook_sheets, source_return_appearances, timeline_records


PROJECT_DIR = Path(__file__).resolve().parent.parent


def age_stats(candidates):
    """Count known ages overall and by gender, with matching averages."""
    groups = {'all': [], 'F': [], 'H': []}
    for candidate in candidates:
        age = candidate['age']
        if age is None:
            continue
        age = int(age)
        groups['all'].append(age)
        if candidate['genre'] in ('F', 'H'):
            groups[candidate['genre']].append(age)
    return {
        group: {
            'counts': dict(sorted(Counter(ages).items())),
            'total': len(ages),
            'average': sum(ages) / len(ages) if ages else None,
        }
        for group, ages in groups.items()
    }


def first_outs(conn, table='Candidats'):
    """Select the worst-placed non-abandonment from each eligible tribe."""
    if table not in ('Candidats', 'AllStars'):
        raise ValueError(f'Unknown candidate table: {table}')
    conn.row_factory = sqlite3.Row
    seasons = conn.execute(f"""
        SELECT saison FROM {table}
        GROUP BY saison HAVING COUNT(DISTINCT tribu) IN (2, 3)
    """).fetchall()
    result = []
    for season in seasons:
        tribes = conn.execute(
            f"SELECT DISTINCT tribu FROM {table} WHERE saison = ? AND tribu IS NOT NULL",
            (season['saison'],),
        ).fetchall()
        for tribe in tribes:
            candidates = conn.execute(f"""
                SELECT saison, tribu, nom, genre, age, place, aban FROM {table}
                WHERE saison = ? AND tribu = ? AND (aban = 0 OR aban IS NULL) AND place IS NOT NULL
                ORDER BY place DESC
            """, (season['saison'], tribe['tribu'])).fetchall()
            if not candidates or (len(candidates) > 1 and candidates[0]['place'] == candidates[1]['place']):
                raise ValueError(f"Cannot identify one first out for {season['saison']} / {tribe['tribu']}")
            result.append(candidates[0])
    return result


def finale_stats(conn, table='Candidats'):
    """Return two-person finals, including joint winners."""
    if table not in ('Candidats', 'AllStars'):
        raise ValueError(f'Unknown candidate table: {table}')
    conn.row_factory = sqlite3.Row
    rows = conn.execute(f"""
        SELECT saison, nom, genre, age, place, aban FROM {table}
        WHERE place IN (1, 2) AND saison != 'Totem Maudit'
        ORDER BY saison, place, nom
    """).fetchall()
    seasons = {}
    for row in rows:
        seasons.setdefault(row['saison'], []).append(dict(row))
    for season, finalists in seasons.items():
        if table == 'AllStars' and len(finalists) == 1:
            continue
        if (len(finalists) != 2 or not any(c['place'] == 1 for c in finalists)
                or any(c['genre'] not in ('F', 'H') for c in finalists)):
            raise ValueError(f"Cannot identify two finalists and their winner(s) for {season}")
        for candidate in finalists:
            if candidate['age'] is not None:
                candidate['age'] = int(candidate['age'])
    return [{'saison': season, 'candidates': finalists} for season, finalists in seasons.items()
            if table != 'AllStars' or len(finalists) == 2]


def elimination_stats(conn):
    """Count genders for the requested elimination groups."""
    groups = {
        'orientation': 'ori = 1 AND (pot = 0 OR pot IS NULL)',
        'third': 'place = 3',
        'ambassadors': 'amb = 1',
    }
    result = {}
    for group, condition in groups.items():
        counts = Counter(row[0] for row in conn.execute(
            f'SELECT genre FROM Candidats WHERE {condition}'
        ))
        result[group] = {
            'F': counts.pop('F', 0), 'H': counts.pop('H', 0),
            'unknown': sum(counts.values()),
        }
    return result


def elimination_candidate_names(conn):
    """Return candidate details for each elimination group without changing counts."""
    groups = {
        'orientation': 'ori = 1 AND (pot = 0 OR pot IS NULL)',
        'third': 'place = 3',
        'ambassadors': 'amb = 1',
    }
    return {
        group: [dict(row) for row in conn.execute(f"""
            SELECT nom, saison, genre, place
            FROM Candidats WHERE {condition}
            ORDER BY saison, nom
        """)]
        for group, condition in groups.items()
    }


def gender_counts(candidates):
    """Count F/H candidates and preserve all other gender values as unknown."""
    counts = Counter(candidate['genre'] for candidate in candidates)
    return {'F': counts.pop('F', 0), 'H': counts.pop('H', 0), 'unknown': sum(counts.values())}


def returnee_sankey(conn):
    """Count every unique initial candidate by gender and linked-return count."""
    counts = Counter()
    for gender, returns in conn.execute("""
        SELECT c.genre, COUNT(r.id_retour)
        FROM Candidats c
        LEFT JOIN Retours r ON r.id_candidat = c.id_candidat
        GROUP BY c.id_candidat
    """):
        counts[(gender if gender in ('F', 'H') else 'unknown', returns)] += 1

    max_returns = max((returns for _, returns in counts), default=0)
    links = [
        {'gender': gender, 'linked_returns': returns, 'candidates': counts[(gender, returns)]}
        for gender in ('F', 'H', 'unknown')
        for returns in range(max_returns + 1)
    ]
    return {
        'basis': 'Unique Candidats.id_candidat records; returns are linked Retours rows.',
        'total_candidates': sum(counts.values()),
        'total_linked_returns': sum(returns * count for (_, returns), count in counts.items()),
        'links': links,
    }


def _normalized(value):
    text = unicodedata.normalize('NFKD', str(value or '').casefold())
    return ' '.join(''.join(char for char in text if not unicodedata.combining(char)).split())


def returnee_ranking(conn, timeline, source_appearances, today=None):
    """Rank linked returnees using wins and orientation outcomes from source rows."""
    today = today or date.today()
    if isinstance(today, datetime):
        today = today.date()
    season_dates = {
        _normalized(season['name']): {
            'start': date.fromisoformat(season['start_date']),
            'end': date.fromisoformat(season['end_date']),
        }
        for season in timeline
    }
    by_appearance = {}
    for appearance in source_appearances:
        key = (
            appearance['source'], _normalized(appearance['season']),
            _normalized(appearance['name']), _normalized(appearance['origin']),
        )
        by_appearance.setdefault(key, []).append(appearance)

    candidates = conn.execute("""
        SELECT c.id_candidat, c.nom, c.saison, c.genre, c.place, c.ori,
               COUNT(r.id_retour) AS return_count
        FROM Candidats c JOIN Retours r ON r.id_candidat = c.id_candidat
        GROUP BY c.id_candidat
    """).fetchall()
    ranking = []
    unmatched_returns = 0
    incomplete_appearances = 0
    for candidate_id, name, initial_season, gender, initial_place, initial_ori, return_count in candidates:
        appearances = [{
            'season': initial_season,
            'place': initial_place,
            'orientation': bool(initial_ori),
            'source': 'Candidats',
        }]
        returns = conn.execute("""
            SELECT r.source, r.saison, c.nom, c.saison
            FROM Retours r JOIN Candidats c ON c.id_candidat = r.id_candidat
            WHERE c.id_candidat = ?
            ORDER BY r.annee, r.saison
        """, (candidate_id,)).fetchall()
        for source, season, candidate_name, origin in returns:
            key = (source, _normalized(season), _normalized(candidate_name), _normalized(origin))
            matches = by_appearance.get(key, [])
            if not matches:
                raise ValueError(f"Linked return has no source row: {candidate_name} / {origin} / {season}")
            source_row = matches.pop(0)
            appearances.append({
                'season': season,
                'place': source_row['place'],
                'orientation': source_row['orientation'],
                'source': source,
            })

        orientation_count = sum(row['orientation'] for row in appearances)
        eligible_appearances = 0
        orientation_seasons = []
        for appearance in appearances:
            dates = season_dates.get(_normalized(appearance['season']))
            if dates is None:
                raise ValueError(f"Missing DATES entry for ranking season: {appearance['season']}")
            if dates['end'] <= today or appearance['orientation']:
                eligible_appearances += 1
            if appearance['orientation']:
                orientation_seasons.append((dates['start'], appearance['season']))

        rate = orientation_count / eligible_appearances if eligible_appearances else None
        comeback_places = [
            row['place'] for row in appearances
            if row['source'] != 'Candidats' and row['place'] is not None
        ]
        comeback_missing_places = sum(
            row['place'] is None for row in appearances if row['source'] != 'Candidats'
        )
        best_comeback_place = min(comeback_places) if comeback_places else None
        known_orientation_seasons = sorted(
            (item for item in orientation_seasons if item[0] is not None),
            key=lambda item: item[0],
        )
        first_orientation = (
            {'season': known_orientation_seasons[0][1],
             'date': known_orientation_seasons[0][0].isoformat()}
            if known_orientation_seasons else None
        )
        last_orientation = (
            {'season': known_orientation_seasons[-1][1],
             'date': known_orientation_seasons[-1][0].isoformat()}
            if known_orientation_seasons else None
        )
        span_days = (
            (known_orientation_seasons[-1][0] - known_orientation_seasons[0][0]).days
            if known_orientation_seasons else None
        )
        score = (
            sum(row['place'] == 1 for row in appearances),
            rate if rate is not None else -1,
            orientation_count,
            span_days if span_days is not None else -1,
            (
                -best_comeback_place
                if orientation_count < 2 and best_comeback_place is not None
                else (float('-inf') if orientation_count < 2 else 0)
            ),
        )
        ranking.append({
            'nom': name,
            'saison_initiale': initial_season,
            'genre': gender if gender in ('F', 'H') else 'unknown',
            'linked_returns': return_count,
            'wins': score[0],
            'orientation_access_rate': rate,
            'orientation_count': orientation_count,
            'eligible_appearances': eligible_appearances,
            'orientation_span_days': span_days,
            'best_comeback_place': best_comeback_place,
            'comeback_appearances_without_placement': comeback_missing_places,
            'best_comeback_place_tiebreak_applied': orientation_count < 2,
            'first_orientation': first_orientation,
            'last_orientation': last_orientation,
            '_score': score,
        })

    ranking.sort(key=lambda row: (
        -row['_score'][0], -row['_score'][1], -row['_score'][2], -row['_score'][3],
        -row['_score'][4], _normalized(row['nom']),
    ))
    cutoff_score = ranking[min(9, len(ranking) - 1)]['_score'] if ranking else None
    selected = []
    previous_score = None
    current_rank = 0
    for index, row in enumerate(ranking, start=1):
        if cutoff_score is not None and row['_score'] < cutoff_score:
            break
        if row['_score'] != previous_score:
            current_rank = index
            previous_score = row['_score']
        row['rank'] = current_rank
        del row['_score']
        selected.append(row)

    return {
        'criteria_order': [
            'wins', 'orientation_access_rate', 'orientation_count', 'orientation_span_days',
            'best_comeback_place_when_orientation_count_is_below_two',
        ],
        'selection': 'Top 10 candidates, including ties on all ranking criteria.',
        'limitations': [
            'Orientation access rate is orientation-flagged appearances divided by eligible appearances.',
            'The workbook has no separate orientation date, so span uses season start dates from DATES.',
            'A season with no end date yet is excluded from the rate denominator unless orientation is already flagged.',
            'Blank ORI? values in completed seasons are treated as not reaching orientation.',
            'Only linked Retours records are ranked; unlinked workbook appearances cannot be attributed to a candidate.',
            'When fewer than two orientations are recorded, the best known comeback place breaks remaining ties; missing places are null and rank behind known places.',
            'comeback_appearances_without_placement reports missing comeback results; a null best_comeback_place means no linked comeback had a known placement.',
        ],
        'unmatched_linked_appearances': unmatched_returns,
        'appearances_without_timeline_dates': incomplete_appearances,
        'candidates': selected,
    }


def returnee_stats(conn):
    """Rank the five leading candidates per gender, including ties."""
    conn.row_factory = sqlite3.Row
    result = {'F': [], 'H': []}
    for gender in result:
        candidates = conn.execute("""
            SELECT c.id_candidat, c.nom, c.saison, c.place, c.aban, COUNT(r.id_retour) AS retours
            FROM Candidats c JOIN Retours r ON r.id_candidat = c.id_candidat
            WHERE c.genre = ?
            GROUP BY c.id_candidat
            ORDER BY retours DESC, c.nom, c.saison
        """, (gender,)).fetchall()
        cutoff = candidates[4]['retours'] if len(candidates) >= 5 else 0
        for candidate in candidates:
            if candidate['retours'] < cutoff:
                break
            appearances = [{'saison': candidate['saison'], 'place': candidate['place'], 'aban': candidate['aban'], 'initiale': True}]
            appearances.extend({
                'saison': row['saison'], 'place': row['place'], 'aban': row['aban'], 'initiale': False,
            } for row in conn.execute("""
                SELECT saison, place, aban FROM Retours WHERE id_candidat = ?
                ORDER BY annee, saison
            """, (candidate['id_candidat'],)))
            result[gender].append({
                'nom': candidate['nom'], 'retours': candidate['retours'], 'participations': appearances,
            })
    return result


def generate_candidate_stats(timeline=None):
    """Generate candidate statistics from SQLite and relevant source workbook fields."""
    if timeline is None:
        timeline = timeline_records(read_workbook_sheets(('DATES',))['DATES'])
    source_rows = read_workbook_sheets(('CLASSIQUES', 'ALLSTARS'))
    source_appearances = source_return_appearances(
        source_rows['CLASSIQUES'], source_rows['ALLSTARS']
    )
    with sqlite3.connect(PROJECT_DIR / 'Donnees_KL.db') as conn:
        conn.row_factory = sqlite3.Row
        candidates = conn.execute("SELECT nom, saison, place, genre, age, aban FROM Candidats ORDER BY saison, nom").fetchall()
        orientation = conn.execute("SELECT nom, saison, place, genre, age, aban FROM Candidats WHERE ori = 1 ORDER BY saison, nom").fetchall()
        eliminated = first_outs(conn)
        finales = finale_stats(conn)
        eliminations = elimination_stats(conn)
        returnees = returnee_stats(conn)
        allstars = conn.execute('SELECT nom, saison, place, genre, age, aban, ori FROM AllStars ORDER BY saison, nom').fetchall()
        allstar_outs = first_outs(conn, 'AllStars')
        allstar_finales = finale_stats(conn, 'AllStars')
        eliminations_with_names = elimination_candidate_names(conn)
        sankey = returnee_sankey(conn)
        ranking = returnee_ranking(conn, timeline, source_appearances)
    gender = gender_counts(eliminated)
    allstar_gender = gender_counts(allstars)
    allstar_first_out_gender = gender_counts(allstar_outs)
    allstar_winners = [
        {'nom': row['nom'], 'saison': row['saison'], 'genre': row['genre']}
        for row in allstars if row['place'] == 1
    ]
    output = {
        'ages': {'all': age_stats(candidates), 'orientation': age_stats(orientation)},
        'age_candidates': {
            'all': [dict(candidate) for candidate in candidates if candidate['age'] is not None],
            'orientation': [dict(candidate) for candidate in orientation if candidate['age'] is not None],
        },
        'finales': finales,
        'eliminations': eliminations,
        'returnees': returnees,
        'allstars': {
            'first_outs': {
                'ages': age_stats(allstar_outs),
                'candidates': [dict(candidate) for candidate in allstar_outs],
                'gender': allstar_first_out_gender,
            },
            'gender': {
                key: {gender: sum(1 for c in allstars if predicate(c) and c['genre'] == gender)
                      for gender in ('F', 'H')}
                for key, predicate in (
                    ('orientation', lambda c: c['ori'] == 1),
                    ('winners', lambda c: c['place'] == 1),
                )
            },
            'finales': allstar_finales,
            'candidates': [dict(candidate) for candidate in allstars],
            'ages': age_stats(allstars),
            'gender_overall': allstar_gender,
            'winners': allstar_winners,
        },
        'first_outs': {
            'gender': {
                'F': gender['F'], 'H': gender['H'], 'unknown': gender['unknown'],
            },
            'ages': age_stats(eliminated),
            'candidates': [dict(candidate) for candidate in eliminated],
        },
        'elimination_candidates': eliminations_with_names,
        'returnee_sankey': sankey,
        'returnee_ranking': ranking,
    }
    with open(PROJECT_DIR / 'candidate_stats.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"[OK] Generated candidate_stats.json ({len(eliminated)} first outs)")
