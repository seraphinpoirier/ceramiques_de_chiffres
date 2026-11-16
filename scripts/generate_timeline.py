"""Generate season chronology from the workbook's DATES worksheet."""

import json
from pathlib import Path

from workbook_data import (
    PROJECT_DIR,
    read_workbook_sheets,
    season_candidate_counts,
    timeline_records,
)


OUTPUT_PATH = PROJECT_DIR / 'timeline_data.json'


def generate_timeline_data():
    """Create timeline_data.json from the DATES worksheet."""
    sheets = read_workbook_sheets(('DATES', 'CLASSIQUES', 'ALLSTARS'))
    candidate_counts = season_candidate_counts(
        sheets['CLASSIQUES'], sheets['ALLSTARS']
    )
    seasons = timeline_records(sheets['DATES'], candidate_counts)
    output = {
        'metadata': {
            'source': 'data/donnees_kohlanta.xlsx (DATES worksheet)',
            'season_count': len(seasons),
            'candidate_count_basis': (
                'Workbook row counts: all CLASSIQUES participant rows including CB?=O, '
                'plus all ALLSTARS participant rows. Counts are not identity-deduplicated.'
            ),
            'classification_note': (
                'Seasons follow the two DATES sections; Île des Héros and La Tribu '
                'Maudite are classified as classic to match the candidate source data.'
            ),
        },
        'seasons': seasons,
    }
    with OUTPUT_PATH.open('w', encoding='utf-8') as output_file:
        json.dump(output, output_file, ensure_ascii=False, indent=2)
    print(f"[OK] Generated {OUTPUT_PATH.name} ({len(seasons)} seasons)")
    return output


if __name__ == '__main__':
    generate_timeline_data()
