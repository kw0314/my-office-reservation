import django, os, sys, json
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
sys.path.insert(0, '.')
django.setup()

from django.test.client import Client

client = Client()

for url in ['/office/', '/office/rooms/', '/view/']:
    response = client.get(url)
    print(f'{url} status={response.status_code} len={len(response.content)}')

response = client.get('/api/office/grid', {'date': '2026-07-04'})
data = json.loads(response.content)
print(f'/api/office/grid rooms: {len(data["rooms"])}')
for r in data['rooms']:
    print(f'  Room id={r["id"]} name={r["name"]!r}')
print(f'reservations: {len(data["reservations"])}')
print(f'blocks: {len(data["blocks"])}')
print(f'slots: {len(data["slots"])}')
