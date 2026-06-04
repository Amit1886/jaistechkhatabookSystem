import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'khatapro.settings')
import django
django.setup()

from django.db import connection
import sqlite3

# Use raw sqlite3 connection to avoid Django's string formatting
db = sqlite3.connect('db.sqlite3')
db.execute('PRAGMA foreign_keys = OFF')

try:
    # Backup data first
    cursor = db.execute('''
        SELECT id, full_name, mobile, created_from, plan_id, user_id
        FROM khataapp_userprofile
    ''')
    data = cursor.fetchall()
    print(f'Backed up {len(data)} records')
    
    # Drop the table
    db.execute('DROP TABLE khataapp_userprofile')
    print('Dropped khataapp_userprofile')
    
    # Create proper table with all columns
    db.execute('''
        CREATE TABLE khataapp_userprofile (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name VARCHAR(255),
            mobile VARCHAR(15),
            address TEXT DEFAULT '',
            business_name VARCHAR(255) DEFAULT '',
            business_type VARCHAR(100) DEFAULT '',
            gst_number VARCHAR(50),
            qr_code VARCHAR(100),
            upi_id VARCHAR(100),
            bank_name VARCHAR(150),
            account_number VARCHAR(50),
            ifsc_code VARCHAR(20),
            profile_picture VARCHAR(100),
            created_from VARCHAR(20) DEFAULT 'signup',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            plan_id BIGINT,
            user_id INTEGER NOT NULL UNIQUE,
            FOREIGN KEY (user_id) REFERENCES accounts_user(id) ON DELETE CASCADE,
            FOREIGN KEY (plan_id) REFERENCES billing_plan(id) ON DELETE SET NULL
        )
    ''')
    print('Created new khataapp_userprofile table')
    
    # Restore data
    for id, full_name, mobile, created_from, plan_id, user_id in data:
        db.execute('''
            INSERT INTO khataapp_userprofile 
            (id, full_name, mobile, address, business_name, business_type, gst_number,
             qr_code, upi_id, bank_name, account_number, ifsc_code, profile_picture,
             created_from, created_at, updated_at, plan_id, user_id)
            VALUES (?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?,
                    ?, datetime('now'), datetime('now'), ?, ?)
        ''', (id, full_name, mobile, '', '', '', None,
              None, None, None, None, None, None,
              created_from, plan_id, user_id))
    
    print(f'Restored {len(data)} records')
    db.commit()
    
except Exception as e:
    print(f'Error: {e}')
    import traceback
    traceback.print_exc()
    db.rollback()
finally:
    # Re-enable FK checks
    db.execute('PRAGMA foreign_keys = ON')
    db.close()
