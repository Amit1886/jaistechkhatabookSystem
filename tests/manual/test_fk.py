#!/usr/bin/env python
import sqlite3

conn = sqlite3.connect('db.sqlite3')
conn.execute('PRAGMA foreign_keys = ON')
cursor = conn.cursor()

# Check if there's already a UserProfile for user_id=35
cursor.execute('SELECT * FROM accounts_userprofile WHERE user_id = 35')
result = cursor.fetchone()
if result:
    print("ERROR: UserProfile already exists for user_id 35:")
    print(result)
else:
    print("OK: No UserProfile exists for user_id 35")

# Try to manually insert
try:
    # First verify both tables have the records
    cursor.execute('SELECT id, username FROM auth_user WHERE id = 35')
    user_result = cursor.fetchone()
    if user_result:
        print(f"✓ User 35 exists: {user_result}")
    else:
        print("✗ User 35 DOES NOT exist!")
        # List last few users
        cursor.execute('SELECT id, username FROM auth_user ORDER BY id DESC LIMIT 3')
        print("Last users:")
        for row in cursor.fetchall():
            print(f"  - {row}")
    
    cursor.execute('SELECT id FROM core_settings_companysettings WHERE id = 21')
    if cursor.fetchone():
        print("✓ CompanySettings 21 exists")
    else:
        print("✗ CompanySettings 21 DOES NOT exist!")
    
    # Check foreign keys
    cursor.execute('PRAGMA foreign_key_list(accounts_userprofile)')
    print("\nForeign keys for UserProfile:")
    for fk in cursor.fetchall():
        print(f"  {fk}")
    
    # Now try the insert
    cursor.execute('''
    INSERT INTO accounts_userprofile (user_id, company_id, full_name, mobile, profile_picture)
    VALUES (35, 21, 'Test', '', '')
    ''')
    conn.commit()
    print("✓ Manual insert successful")
    
except Exception as e:
    print(f"✗ Manual insert failed: {e}")
    import traceback
    traceback.print_exc()
finally:
    conn.close()
