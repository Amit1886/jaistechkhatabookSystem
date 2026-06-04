#!/usr/bin/env python
import sqlite3

conn = sqlite3.connect('db.sqlite3')
cursor = conn.cursor()

# Get the schema for auth_user
cursor.execute('SELECT sql FROM sqlite_master WHERE type="table" AND name="auth_user"')
result = cursor.fetchone()
if result:
    print("auth_user schema:")
    print(result[0])
else:
    print("Table not found")

conn.close()
