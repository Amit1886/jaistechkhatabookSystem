#!/usr/bin/env python
import sqlite3

conn = sqlite3.connect('db.sqlite3')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Check core_settings_companysettings table
print("=== core_settings_companysettings ===")
cursor.execute('SELECT * FROM core_settings_companysettings ORDER BY id DESC LIMIT 5')
rows = cursor.fetchall()
for row in rows:
    print(dict(row))

# Check accounts_userprofile table
print("\n=== accounts_userprofile ===")
cursor.execute('SELECT * FROM accounts_userprofile ORDER BY id DESC LIMIT 5')
rows = cursor.fetchall()
for row in rows:
    print(dict(row))

# Check for orphaned records
print("\n=== Check for orphaned company_id ===")
cursor.execute('''
SELECT up.id, up.user_id, up.company_id, cs.id as company_exists
FROM accounts_userprofile up
LEFT JOIN core_settings_companysettings cs ON up.company_id = cs.id
WHERE up.company_id IS NOT NULL AND cs.id IS NULL
''')
rows = cursor.fetchall()
if rows:
    print("Found orphaned records:")
    for row in rows:
        print(dict(row))
else:
    print("No orphaned records found")

conn.close()
