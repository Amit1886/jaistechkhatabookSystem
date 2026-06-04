#!/usr/bin/env python
import sqlite3

conn = sqlite3.connect('db.sqlite3')
cursor = conn.cursor()

print('=== Check Free Plan ===')
cursor.execute("SELECT id, name, price FROM billing_plan WHERE price = 0 OR name LIKE '%Free%'")
for row in cursor.fetchall():
    print(row)

print('\n=== Check existing khataapp_userprofile records ===')
cursor.execute('SELECT user_id, plan_id FROM khataapp_userprofile LIMIT 7')
for row in cursor.fetchall():
    print(f'User: {row[0]}, Plan: {row[1]}')

print('\n=== Check if plan_id 1 exists ===')
cursor.execute('SELECT id, name FROM billing_plan WHERE id = 1')
result = cursor.fetchone()
print('Plan 1:', result)

print('\n=== All billing plans ===')
cursor.execute('SELECT id, name FROM billing_plan')
for row in cursor.fetchall():
    print(row)

conn.close()
