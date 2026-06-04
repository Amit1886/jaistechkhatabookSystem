#!/usr/bin/env python
import sqlite3

conn = sqlite3.connect('db.sqlite3')
conn.execute('PRAGMA foreign_keys = ON')
cursor = conn.cursor()

# Test creating a company and userprofile manually
try:
    cursor.execute('''
    INSERT INTO core_settings_companysettings (company_name, logo, mobile, email)
    VALUES ('test_company_manual', '', '', '')
    ''')
    conn.commit()
    print("✓ CompanySettings insert successful")
    
    # Get the last company id
    cursor.execute('SELECT last_insert_rowid()')
    company_id = cursor.fetchone()[0]
    print(f"  Company ID: {company_id}")
    
    # Now test inserting a userprofile with this company_id
    # First create a test user if it doesn't exist
    cursor.execute('''
    SELECT id FROM auth_user WHERE username = 'test_manual_user'
    ''')
    result = cursor.fetchone()
    if not result:
        print("Creating test user...")
        cursor.execute('''
        INSERT INTO auth_user (password, last_login, is_superuser, first_name, last_name, is_staff, is_active, date_joined, username, email)
        VALUES ('pbkdf2_sha256$dummy', NULL, 0, '', '', 0, 1, datetime('now'), 'test_manual_user', 'test_manual@example.com')
        ''')
        conn.commit()
        cursor.execute('SELECT last_insert_rowid()')
        user_id = cursor.fetchone()[0]
        print(f"  User ID: {user_id}")
    else:
        user_id = result[0]
        print(f"  Using existing user ID: {user_id}")
    
    # Now try to insert UserProfile
    cursor.execute('''
    INSERT INTO accounts_userprofile (user_id, company_id, full_name, mobile)
    VALUES (?, ?, 'Test Name', 'test_mobile')
    ''', (user_id, company_id))
    conn.commit()
    print("✓ UserProfile insert successful")
    
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
finally:
    conn.close()
