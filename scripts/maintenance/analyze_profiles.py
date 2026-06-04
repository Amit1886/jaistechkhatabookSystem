#!/usr/bin/env python
import sqlite3

conn = sqlite3.connect('db.sqlite3')
cursor = conn.cursor()

print('=== khataapp_userprofile records ===')
cursor.execute('SELECT id, user_id FROM khataapp_userprofile')
profiles = cursor.fetchall()
print(f'Total profiles: {len(profiles)}')
for pid, uid in profiles:
    print(f'  Profile {pid} -> User {uid}')

print('\n=== Check FK constraint violations ===')
cursor.execute('''
SELECT ku.user_id 
FROM khataapp_userprofile ku
LEFT JOIN accounts_user au ON ku.user_id = au.id
WHERE au.id IS NULL
''')
orphaned = cursor.fetchall()
if orphaned:
    print(f'Orphaned profiles (users missing): {len(orphaned)}')
    for (uid,) in orphaned:
        print(f'  User {uid} does not exist')
else:
    print('No orphaned profiles found')

print('\n=== Users without profiles ===')
cursor.execute('''
SELECT au.id, au.username
FROM accounts_user au
LEFT JOIN khataapp_userprofile ku ON au.id = ku.user_id
WHERE ku.id IS NULL
ORDER BY au.id
''')
missing = cursor.fetchall()
print(f'Users without profiles: {len(missing)}')
for uid, uname in missing:
    print(f'  {uid}: {uname}')

conn.close()
