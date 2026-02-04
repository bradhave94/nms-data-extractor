import json
from pathlib import Path

files = sorted(Path('data/json').glob('*.json'))
for f in files:
    if f.name != 'localization.json':
        data = json.load(open(f, encoding='utf-8'))
        size_kb = f.stat().st_size / 1024
        print(f'{f.name:30} {len(data):5} items  {size_kb:8.1f} KB')
