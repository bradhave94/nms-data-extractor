import json

items_to_find = ['Atlas Fireworks', 'Wiring Loom', 'FREIGHTER RECOLOURING', 'Freighter Recolouring']
files = ['Buildings.json', 'Others.json', 'Curiosities.json', 'Products.json']

for filename in files:
    data = json.load(open(f'data/json/{filename}', encoding='utf-8'))
    for item in data:
        name = item.get('Name', '')
        if any(search in name for search in items_to_find):
            print(f"{item['Name']:40} -> {filename:25} Group: {item.get('Group', '')}")
