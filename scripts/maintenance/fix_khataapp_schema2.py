import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'khatapro.settings')
import django
django.setup()

from django.db import connection

# Recreate khataapp_userprofile with ALL columns and proper FKs
with connection.cursor() as cursor:
    # Disable FK checks
    cursor.execute('PRAGMA foreign_keys = OFF')
    
    try:
        # Backup data first
        cursor.execute('''
            SELECT id, full_name, mobile, created_from, plan_id, user_id
            FROM khataapp_userprofile
        ''')
        data = cursor.fetchall()
        print(f'Backed up {len(data)} records')
        
        # Drop the table
        cursor.execute('DROP TABLE khataapp_userprofile')
        print('Dropped khataapp_userprofile')
        
        # Create proper table with all columns
        cursor.execute('''
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
        
        # Restore data with defaults for new columns
        for id, full_name, mobile, created_from, plan_id, user_id in data:
            cursor.execute('''
                INSERT INTO khataapp_userprofile 
                (id, full_name, mobile, address, business_name, business_type, gst_number,
                 qr_code, upi_id, bank_name, account_number, ifsc_code, profile_picture,
                 created_from, created_at, updated_at, plan_id, user_id)
                VALUES (?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?)
            ''', (id, full_name, mobile, '', '', '', None,
                  None, None, None, None, None, None,
                  created_from, 'CURRENT_TIMESTAMP', 'CURRENT_TIMESTAMP', plan_id, user_id))
        
        print(f'Restored {len(data)} records')
        connection.commit()
        
    except Exception as e:
        print(f'Error: {e}')
        import traceback
        traceback.print_exc()
        connection.rollback()
    finally:
        # Re-enable FK checks
        cursor.execute('PRAGMA foreign_keys = ON')
        connection.commit()
