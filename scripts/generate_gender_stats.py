"""Generate gender totals for the 'Et les femmes ?' section."""

import json
import sqlite3
from collections import Counter

from workbook_data import PROJECT_DIR, read_workbook_sheets


def _gender_totals(genders):
    counts = Counter(gender for gender in genders if gender in ('F', 'H'))
    return {
        'H': counts['H'],
        'F': counts['F'],
        'total': counts['H'] + counts['F'],
    }


def _flagged(value):
    if isinstance(value, str):
        return value.strip().casefold() in ('o', 'oui', '1', 'true')
    return value is True or value == 1


def _classic_category_stats(rows):
    if not rows:
        raise ValueError('CLASSIQUES worksheet is empty')
    headers = {name: index for index, name in enumerate(rows[0])}
    required = ('GENRE', 'ORI?', 'POT?', 'PLACE')
    missing = [column for column in required if column not in headers]
    if missing:
        raise ValueError(f"CLASSIQUES: missing columns {missing}")

    selections = {
        'ori': lambda row: _flagged(row[headers['ORI?']]),
        'pot': lambda row: _flagged(row[headers['POT?']]),
        'place': lambda row: row[headers['PLACE']] == 1,
    }
    selected_genders = {key: [] for key in selections}
    for row in rows[1:]:
        if not row or not any(value is not None for value in row):
            continue
        gender = str(row[headers['GENRE']] or '').strip().upper()
        for key, predicate in selections.items():
            if predicate(row):
                selected_genders[key].append(gender)
    return {key: _gender_totals(genders) for key, genders in selected_genders.items()}


def calculate_gender_stats(conn, classic_rows):
    """Keep overall classic entrants separate; count all CLASSIQUES appearances for outcomes."""
    overall = dict(conn.execute("""
        SELECT genre, COUNT(*) FROM Candidats
        WHERE genre IS NOT NULL GROUP BY genre
    """).fetchall())
    stats = {
        'overall': {
            'H': overall.get('H', 0),
            'F': overall.get('F', 0),
            'total': overall.get('H', 0) + overall.get('F', 0),
        }
    }
    stats.update(_classic_category_stats(classic_rows))
    return stats


def generate_gender_stats():
    """Generate overall and outcome counts, including every classic comeback row."""
    classic_rows = read_workbook_sheets(('CLASSIQUES',))['CLASSIQUES']
    with sqlite3.connect(PROJECT_DIR / 'Donnees_KL.db') as conn:
        stats = calculate_gender_stats(conn, classic_rows)

    output = {
        'metadata': {
            'generated': True,
            'overall_source': 'Candidats database table (classic initial entries; excludes CB? returns)',
            'outcome_source': (
                'All CLASSIQUES worksheet rows, including CB?=O returns; each appearance '
                'is counted once, including rows not linked in Retours.'
            ),
        },
        'stats': stats,
    }

    with (PROJECT_DIR / 'gender_stats.json').open('w', encoding='utf-8') as output_file:
        json.dump(output, output_file, ensure_ascii=False, indent=2)

    print("Generated gender_stats.json")
    print(f"  Overall: {stats['overall']['H']} H, {stats['overall']['F']} F (total: {stats['overall']['total']})")
    print(f"  Orientation: {stats['ori']['H']} H, {stats['ori']['F']} F (total: {stats['ori']['total']})")
    print(f"  Poteaux: {stats['pot']['H']} H, {stats['pot']['F']} F (total: {stats['pot']['total']})")
    print(f"  Place 1 (Winners): {stats['place']['H']} H, {stats['place']['F']} F (total: {stats['place']['total']})")


if __name__ == '__main__':
    generate_gender_stats()
