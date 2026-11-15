"""Generate candidate statistics from SQLite."""

import json
import sqlite3
from collections import Counter
from pathlib import Path


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


def generate_candidate_stats():
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
    gender = Counter(candidate['genre'] for candidate in eliminated)
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
        },
        'first_outs': {
            'gender': {
                'F': gender['F'], 'H': gender['H'],
                'unknown': len(eliminated) - gender['F'] - gender['H'],
            },
            'ages': age_stats(eliminated),
            'candidates': [dict(candidate) for candidate in eliminated],
        },
    }
    with open(PROJECT_DIR / 'candidate_stats.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"[OK] Generated candidate_stats.json ({len(eliminated)} first outs)")
