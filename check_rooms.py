import django, os, sys, json
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
sys.path.insert(0, '.')
django.setup()

from reservations.views import office_grid_api
from django.test.client import RequestFactory

factory = RequestFactory()
request = factory.get('/api/office/grid', {'date': '2026-07-04'})
response = office_grid_api(request)
data = json.loads(response.content)

print('=== API Response ===')
print(f'Date: {data["date"]}')
print(f'Rooms count: {len(data["rooms"])}')
for r in data['rooms']:
    print(f'  id={r["id"]}, name={r["name"]!r}, requires_approval={r["requires_approval"]}')
print(f'Reservations count: {len(data["reservations"])}')
print(f'Blocks count: {len(data["blocks"])}')
print(f'Slots count: {len(data["slots"])}')
print(f'Open: {data["open"]}, Close: {data["close"]}')
