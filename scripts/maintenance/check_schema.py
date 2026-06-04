#!/usr/bin/env python
import sqlite3

conn = sqlite3.connect('db.sqlite3')
cursor = conn.cursor()

# Get the schema
cursor.execute('SELECT sql FROM sqlite_master WHERE type="table" AND name="accounts_userprofile"')
result = cursor.fetchone()
if result:
    print("Current schema:")
    print(result[0])
else:
    print("Table not found")

# Check for FK constraints
cursor.execute('PRAGMA foreign_key_list(accounts_userprofile)')
fks = cursor.fetchall()
print("\nForeign Key Constraints:")
for fk in fks:
    print(fk)

conn.close()
