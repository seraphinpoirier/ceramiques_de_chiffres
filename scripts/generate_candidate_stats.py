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


def first_outs(conn):
    """Select the worst-placed non-abandonment from each eligible tribe."""
    conn.row_factory = sqlite3.Row
    seasons = conn.execute("""
        SELECT saison FROM Candidats
        GROUP BY saison HAVING COUNT(DISTINCT tribu) IN (2, 3)
    """).fetchall()
    result = []
    for season in seasons:
        tribes = conn.execute(
            "SELECT DISTINCT tribu FROM Candidats WHERE saison = ? AND tribu IS NOT NULL",
            (season['saison'],),
        ).fetchall()
        for tribe in tribes:
            candidates = conn.execute("""
                SELECT saison, tribu, nom, genre, age, place FROM Candidats
                WHERE saison = ? AND tribu = ? AND (aban = 0 OR aban IS NULL) AND place IS NOT NULL
                ORDER BY place DESC
            """, (season['saison'], tribe['tribu'])).fetchall()
            if not candidates or (len(candidates) > 1 and candidates[0]['place'] == candidates[1]['place']):
                raise ValueError(f"Cannot identify one first out for {season['saison']} / {tribe['tribu']}")
            result.append(candidates[0])
    return result


def finale_stats(conn):
    """Return two-person finals, including joint winners."""
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT saison, nom, genre, age, place FROM Candidats
        WHERE place IN (1, 2) AND saison != 'Totem Maudit'
        ORDER BY saison, place, nom
    """).fetchall()
    seasons = {}
    for row in rows:
        seasons.setdefault(row['saison'], []).append(dict(row))
    for season, finalists in seasons.items():
        if (len(finalists) != 2 or not any(c['place'] == 1 for c in finalists)
                or any(c['genre'] not in ('F', 'H') for c in finalists)):
            raise ValueError(f"Cannot identify two finalists and their winner(s) for {season}")
        for candidate in finalists:
            if candidate['age'] is not None:
                candidate['age'] = int(candidate['age'])
    return [{'saison': season, 'candidates': finalists} for season, finalists in seasons.items()]


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
    """Rank candidates by linked returns, including ties at fifth place."""
    conn.row_factory = sqlite3.Row
    result = {'F': [], 'H': []}
    for gender in result:
        candidates = conn.execute("""
            SELECT c.id_candidat, c.nom, c.saison, c.place, COUNT(r.id_retour) AS retours
            FROM Candidats c JOIN Retours r ON r.id_candidat = c.id_candidat
            WHERE c.genre = ?
            GROUP BY c.id_candidat
            ORDER BY retours DESC, c.nom, c.saison
        """, (gender,)).fetchall()
        cutoff = candidates[4]['retours'] if len(candidates) >= 5 else 0
        for candidate in candidates:
            if candidate['retours'] < cutoff:
                break
            appearances = [{'saison': candidate['saison'], 'place': candidate['place'], 'initiale': True}]
            appearances.extend({
                'saison': row['saison'], 'place': row['place'], 'initiale': False,
            } for row in conn.execute("""
                SELECT saison, place FROM Retours WHERE id_candidat = ?
                ORDER BY annee, saison
            """, (candidate['id_candidat'],)))
            result[gender].append({
                'nom': candidate['nom'], 'retours': candidate['retours'], 'participations': appearances,
            })
    return result


def generate_candidate_stats():
    with sqlite3.connect(PROJECT_DIR / 'Donnees_KL.db') as conn:
        conn.row_factory = sqlite3.Row
        candidates = conn.execute("SELECT nom, saison, place, genre, age FROM Candidats ORDER BY saison, nom").fetchall()
        orientation = conn.execute("SELECT nom, saison, place, genre, age FROM Candidats WHERE ori = 1 ORDER BY saison, nom").fetchall()
        eliminated = first_outs(conn)
        finales = finale_stats(conn)
        eliminations = elimination_stats(conn)
        returnees = returnee_stats(conn)
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
