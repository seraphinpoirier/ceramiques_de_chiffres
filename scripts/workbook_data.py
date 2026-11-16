"""Helpers for reading the project workbook without modifying the source file."""

import shutil
import tempfile
import unicodedata
from pathlib import Path

import openpyxl


PROJECT_DIR = Path(__file__).resolve().parent.parent
WORKBOOK_PATH = PROJECT_DIR / 'data' / 'donnees_kohlanta.xlsx'


def normalized_text(value):
    """Normalize names for matching worksheet season labels."""
    text = unicodedata.normalize('NFKD', str(value or '').casefold())
    return ' '.join(''.join(char for char in text if not unicodedata.combining(char)).split())


def read_workbook_sheets(sheets, workbook_path=WORKBOOK_PATH):
    """Return worksheet values from a temporary copy of the source workbook."""
    with tempfile.TemporaryDirectory(prefix='kl-workbook-') as temp_dir:
        copy_path = Path(temp_dir) / Path(workbook_path).name
        shutil.copy2(workbook_path, copy_path)
        workbook = openpyxl.load_workbook(copy_path, read_only=True, data_only=True)
        try:
            missing = [sheet for sheet in sheets if sheet not in workbook.sheetnames]
            if missing:
                raise ValueError(f"Workbook is missing worksheet(s): {', '.join(missing)}")
            return {
                sheet: list(workbook[sheet].iter_rows(values_only=True))
                for sheet in sheets
            }
        finally:
            workbook.close()


def season_candidate_counts(classic_rows, all_stars_rows):
    """Count participant rows by season and source worksheet.

    All non-empty CLASSIQUES rows count, including rows marked CB?=O. ALLSTARS
    counts every non-empty participant row. Counts are row counts, not linked
    identities, so unlinked and repeated appearances remain represented.
    """
    counts = {}
    for source, rows in (
        ('CLASSIQUES', classic_rows),
        ('ALLSTARS', all_stars_rows),
    ):
        if not rows:
            continue
        headers = {name: index for index, name in enumerate(rows[0])}
        missing = [column for column in ('SAISON', 'NOM') if column not in headers]
        if missing:
            raise ValueError(f"{source}: missing columns {missing}")
        for line, row in enumerate(rows[1:], start=2):
            if not row or not any(value is not None for value in row):
                continue
            season = row[headers['SAISON']]
            name = row[headers['NOM']]
            if not str(season or '').strip() or not str(name or '').strip():
                raise ValueError(f"{source} row {line}: missing season or candidate name")
            key = normalized_text(season)
            source_counts = counts.setdefault(key, {'CLASSIQUES': 0, 'ALLSTARS': 0})
            source_counts[source] += 1
    return counts


def timeline_records(rows, candidate_counts=None):
    """Parse DATES rows into dated seasons, including the two source sections."""
    candidate_counts = candidate_counts or {}
    records = []
    section = 'classic'
    previous_number = None
    pending = None

    for row_number, row in enumerate(rows, start=1):
        number = row[0] if len(row) > 0 else None
        name = row[1] if len(row) > 1 else None
        date_value = row[2] if len(row) > 2 else None
        if number is not None and name and date_value is not None:
            if previous_number is not None and number <= previous_number:
                section = 'all_stars'
            if pending is not None:
                raise ValueError(f"DATES row {row_number}: previous season has no end date")
            pending = {
                'number': int(number),
                'name': str(name).strip(),
                'start_date': date_value,
                'source_section': section,
                'series': section,
            }
            previous_number = int(number)
        elif number is None and name is None and date_value is not None:
            if pending is None:
                raise ValueError(f"DATES row {row_number}: end date without a season")
            if date_value < pending['start_date']:
                raise ValueError(f"DATES row {row_number}: end date precedes start date")
            pending['end_date'] = date_value
            pending['duration_days'] = (date_value - pending['start_date']).days
            # These are classic seasons in the candidate source data, even when
            # they appear in DATES' special-edition section.
            if pending['name'].casefold() in (
                'île des héros', 'tribu maudite', 'la tribu maudite',
            ):
                pending['series'] = 'classic'
            pending['classification'] = (
                'All Stars' if pending['series'] == 'all_stars' else 'classic'
            )
            pending['id'] = f"{pending['source_section']}-{pending['number']}"
            source_counts = candidate_counts.get(
                normalized_text(pending['name']), {'CLASSIQUES': 0, 'ALLSTARS': 0}
            )
            pending['candidate_counts_by_source'] = dict(source_counts)
            pending['candidate_count'] = sum(source_counts.values())
            pending['start_date'] = pending['start_date'].date().isoformat()
            pending['end_date'] = pending['end_date'].date().isoformat()
            records.append(pending)
            pending = None

    if pending is not None:
        raise ValueError(f"DATES season {pending['name']!r} has no end date")
    if not records:
        raise ValueError('DATES contains no complete seasons')
    unmatched = set(candidate_counts) - {normalized_text(season['name']) for season in records}
    if unmatched:
        raise ValueError(f"Candidate seasons missing from DATES: {', '.join(sorted(unmatched))}")
    records.sort(key=lambda season: season['start_date'])
    return records


def source_return_appearances(classic_rows, all_stars_rows):
    """Extract marked classic returns and All Stars appearances with source flags."""
    appearances = []
    for source, rows in (('CLASSIQUES', classic_rows), ('ALLSTARS', all_stars_rows)):
        if not rows:
            continue
        headers = {name: index for index, name in enumerate(rows[0])}
        origin_column = 'SAISON ORIGINALE' if source == 'CLASSIQUES' else 'INITIALE'
        required = ('SAISON', 'NOM', 'PLACE', 'ORI?', origin_column)
        if source == 'CLASSIQUES':
            required += ('CB?',)
        missing = [column for column in required if column not in headers]
        if missing:
            raise ValueError(f"{source}: missing columns {missing}")

        for line, row in enumerate(rows[1:], start=2):
            if not any(value is not None for value in row):
                continue
            if source == 'CLASSIQUES':
                comeback = row[headers['CB?']]
                if str(comeback or '').strip().casefold() != 'o':
                    continue
            appearances.append({
                'source': source,
                'line': line,
                'season': row[headers['SAISON']],
                'name': row[headers['NOM']],
                'origin': row[headers[origin_column]],
                'orientation': bool(row[headers['ORI?']]),
                'place': row[headers['PLACE']] if isinstance(row[headers['PLACE']], int) else None,
            })
    return appearances
