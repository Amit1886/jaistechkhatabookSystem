#!/usr/bin/env python
import sqlite3
from datetime import datetime

conn = sqlite3.connect('db.sqlite3')
cursor = conn.cursor()

# Get users without profiles
cursor.execute('''
SELECT au.id, au.username
FROM accounts_user au
LEFT JOIN khataapp_userprofile ku ON au.id = ku.user_id
WHERE ku.id IS NULL
ORDER BY au.id
''')
missing_users = cursor.fetchall()

print(f"Creating profiles for {len(missing_users)} users...")

now = datetime.now().isoformat()

# Bulk insert using raw SQL
for user_id, username in missing_users:
    try:
        cursor.execute('''
        INSERT INTO khataapp_userprofile (
            user_id, plan_id, full_name, mobile, address,
            business_name, business_type, gst_number, qr_code, upi_id,
            bank_name, account_number, ifsc_code, profile_picture,
            created_from, created_at, updated_at
        ) VALUES (
            ?, NULL, ?, '', '',
            '', '', NULL, '', NULL,
            NULL, NULL, NULL, '',
            'signup', ?, ?
        )
        ''', (user_id, username, now, now))
        print(f"Created profile for {username}")
    except Exception as e:
        print(f"Error for {username}: {e}")

conn.commit()

# Verify
cursor.execute('SELECT COUNT(*) FROM khataapp_userprofile')
profile_count = cursor.fetchone()[0]

cursor.execute('SELECT COUNT(*) FROM accounts_user')
user_count = cursor.fetchone()[0]

print(f"\nFinal: Users={user_count}, Profiles={profile_count}")

conn.close()
