"""Apply a reviewed export's Old/New Order mapping to the existing Notion pages."""
import argparse
import csv
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from fetch_notion import CFG, DB_TITLES, TOKEN, api, query_all

ORDERED_DATABASES = {title: key for key, title in DB_TITLES.items()
                     if key not in ('site_content', 'teaching')}


def read_mapping(path):
    mapping = {}
    with path.open(encoding='utf-8-sig', newline='') as stream:
        for entry in csv.DictReader(stream):
            table = mapping.setdefault(entry['Database'], {})
            page = str(UUID(entry['Page'].rsplit('/', 1)[-1]))
            if page in table:
                raise ValueError(f'Duplicate page {page}')
            old = Decimal(entry['Old']) if entry['Old'] else None
            table[page] = (old, int(entry['New']))
    if mapping.keys() != ORDERED_DATABASES.keys():
        raise ValueError('Expected all eight ordered databases')
    for name, table in mapping.items():
        if sorted(new for old, new in table.values()) != list(range(1, len(table) + 1)):
            raise ValueError(f'{name}: expected unique, consecutive positive integers')
    return mapping


def planned_changes(mapping):
    changes = []
    for name, table in mapping.items():
        source = CFG['data_sources'][ORDERED_DATABASES[name]]
        live = {row['id']: row for row in query_all(source)}
        if table.keys() - live.keys():
            raise ValueError(f'{name}: exported pages missing from live DB; refresh the export')
        for page, row in live.items():
            field = row['properties'].get('Order', {})
            if field.get('type') != 'number':
                raise ValueError(f'{name}: expected numeric Order on {page}')
            value = field['number']
            current = Decimal(str(value)) if value is not None else None
            if page not in table:
                if current is not None:
                    raise ValueError(f'{name}: numbered page added after export; refresh the export')
                continue
            old, new = table[page]
            if current == new:
                continue
            if current != old:
                raise ValueError(f'{name}: Order changed since export on {page}: {current}')
            changes.append((page, new))
    return changes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mapping', type=Path)
    parser.add_argument('--apply', action='store_true', help='write the reviewed changes')
    args = parser.parse_args()
    mapping = read_mapping(args.mapping)
    if not TOKEN:
        parser.exit(1, 'Set NOTION_TOKEN for the target workspace.\n')
    changes = planned_changes(mapping)
    print(f'{len(changes)} existing pages need an Order update.')
    if args.apply:
        for page, number in changes:
            api('PATCH', '/pages/' + page, {'properties': {'Order': {'number': number}}})
        if planned_changes(mapping):
            raise RuntimeError('Order changes remain after migration. Rerun with the same mapping.')
        print('Verified all mapped orders in Notion.')


if __name__ == '__main__':
    main()
