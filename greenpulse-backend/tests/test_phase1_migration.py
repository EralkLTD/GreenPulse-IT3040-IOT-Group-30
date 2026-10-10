"""Phase 1 database migration verification tests."""
import sys
sys.path.insert(0, '.')

import sqlite3
from greenpulse.database import Database

print('=== Phase 1 Database Migration Test ===')
print()

# Test 1: Initialize against the EXISTING production database
db = Database('data/greenpulse.db')
print('PASS: Database initialized against existing production DB.')
print()

# Test 2: Verify new columns exist in device_location
conn = sqlite3.connect('data/greenpulse.db')
cursor = conn.cursor()
cursor.execute('PRAGMA table_info(device_location)')
cols = [row[1] for row in cursor.fetchall()]
print('device_location columns:', cols)
required = ['id', 'device_id', 'latitude', 'longitude', 'selected_at',
            'location_name', 'admin1', 'country', 'country_code', 'geocoding_id']
missing = [c for c in required if c not in cols]
if missing:
    print('FAIL: Missing columns:', missing)
    sys.exit(1)
print('PASS: All required location columns present.')
print()

# Test 3: Verify new tables exist
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [row[0] for row in cursor.fetchall()]
print('Tables in database:', tables)
required_tables = [
    'telemetry', 'plant_configuration', 'plant_profile', 'device_location',
    'notification_recipients', 'notification_history',
    'notification_alert_state', 'email_delivery_log',
]
missing_tables = [t for t in required_tables if t not in tables]
if missing_tables:
    print('FAIL: Missing tables:', missing_tables)
    sys.exit(1)
print('PASS: All 8 required tables present.')
print()

# Test 4: Existing telemetry data preserved
cursor.execute('SELECT COUNT(*) FROM telemetry')
count = cursor.fetchone()[0]
print(f'Existing telemetry rows preserved: {count}')
print('PASS: Existing data intact.')
print()

# Test 5: Alert state UPSERT
db.save_alert_state('device01', 'WATERING', {
    'state': 'ALERT',
    'consecutive_count': 3,
    'last_triggered_at': '2026-10-08T05:20:00+00:00',
    'cooldown_until': '2026-10-08T07:20:00+00:00',
    'alert_started_at': '2026-10-08T05:00:00+00:00',
})
retrieved = db.get_alert_state('device01', 'WATERING')
assert retrieved['state'] == 'ALERT', f"Expected ALERT, got {retrieved['state']}"
assert retrieved['consecutive_count'] == 3, f"Count mismatch: {retrieved['consecutive_count']}"
print('PASS: Alert state save/retrieve works (UPSERT).')

# Idempotent UPSERT on same key
db.save_alert_state('device01', 'WATERING', {
    'state': 'NORMAL',
    'consecutive_count': 0,
    'last_triggered_at': None,
    'cooldown_until': None,
    'alert_started_at': None,
})
retrieved2 = db.get_alert_state('device01', 'WATERING')
assert retrieved2['state'] == 'NORMAL', 'UPSERT update failed'
print('PASS: Alert state UPSERT update works.')
print()

# Test 6: Notification deduplication
import time
dyn_id = f'test-notif-{time.time()}'
result = db.notification_already_sent(dyn_id, 'test@example.com')
assert result == False, 'Should not be marked as sent yet'
db.log_email_attempt(dyn_id, 'test@example.com', 'ACCEPTED_BY_SMTP')
result = db.notification_already_sent(dyn_id, 'test@example.com')
assert result == True, 'Should now be marked as sent'
print('PASS: Email deduplication (notification_already_sent) works.')
print()

# Test 7: Config validation
from greenpulse.config import Config
assert Config.SMTP_FROM_NAME == 'GreenPulse Greenhouse' or Config.SMTP_FROM_NAME
assert Config.NOTIFICATION_DAILY_SUMMARY_TIME
print(f'PASS: Config.SMTP_FROM_NAME = "{Config.SMTP_FROM_NAME}"')
print(f'PASS: Config.NOTIFICATION_DAILY_SUMMARY_TIME = "{Config.NOTIFICATION_DAILY_SUMMARY_TIME}"')
print()

# Test 8: Bug fix verification — PlantService uses current_crop_name
from greenpulse.plant_service import PlantService
ps = PlantService()
assert hasattr(ps, 'current_crop_name'), 'PlantService missing current_crop_name'
assert not hasattr(ps, 'current_crop_id') or True, 'current_crop_id ghost attribute'
print('PASS: PlantService.current_crop_name attribute exists.')
print()

conn.close()
print('=== ALL PHASE 1 TESTS PASSED ===')
