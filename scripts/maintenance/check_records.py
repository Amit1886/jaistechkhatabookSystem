#!/usr/bin/env python
import sqlite3

conn = sqlite3.connect('db.sqlite3')
cursor = conn.cursor()

# Check if company 22 exists
cursor.execute('SELECT * FROM core_settings_companysettings WHERE id = 22')
result = cursor.fetchone()
print(f"CompanySettings ID 22: {result}")

# Check if user 36 exists
cursor.execute('SELECT id, username FROM auth_user WHERE id = 36')
result = cursor.fetchone()
print(f"User ID 36: {result}")

# Check if user 37 exists
cursor.execute('SELECT id, username FROM auth_user WHERE id = 37')
result = cursor.fetchone()
print(f"User ID 37: {result}")

# Try to manually insert with FK enabled
conn.execute('PRAGMA foreign_keys = ON')

try:
    cursor.execute('''
    INSERT INTO accounts_userprofile (user_id, company_id, full_name, mobile)
    VALUES (37, 22, 'Test', '')
    ''')
    conn.commit()
    print("✓ Inserted successfully")
except Exception as e:
    print(f"✗ Error: {e}")
    conn.close()
