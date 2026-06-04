import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'khatapro.settings')
import django
django.setup()

from django.db import connection

# Disable FK checks, drop and recreate khataapp_userprofile table
with connection.cursor() as cursor:
    # Disable FK checks
    cursor.execute('PRAGMA foreign_keys = OFF')
    
    try:
        # Get the original table schema
        cursor.execute("PRAGMA table_info(khataapp_userprofile)")
        columns = cursor.fetchall()
        print('khataapp_userprofile columns:')
        for col in columns:
            print(f'  {col}')
        
        # Rename old table
        cursor.execute('ALTER TABLE khataapp_userprofile RENAME TO khataapp_userprofile_old')
        print('\nRenamed khataapp_userprofile to khataapp_userprofile_old')
        
        # Create new table with correct FKs
        cursor.execute('''
            CREATE TABLE khataapp_userprofile (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name VARCHAR(150) NOT NULL,
                mobile VARCHAR(15),
                created_from VARCHAR(50),
                plan_id INTEGER,
                user_id INTEGER NOT NULL UNIQUE,
                FOREIGN KEY (user_id) REFERENCES accounts_user(id) ON DELETE CASCADE,
                FOREIGN KEY (plan_id) REFERENCES billing_plan(id) ON DELETE SET NULL
            )
        ''')
        print('Created new khataapp_userprofile table with correct FKs')
        
        # Copy data from old table
        cursor.execute('''
            INSERT INTO khataapp_userprofile 
            SELECT id, full_name, mobile, created_from, plan_id, user_id 
            FROM khataapp_userprofile_old
        ''')
        print(f'Migrated UserProfile records')
        
        # Drop old table
        cursor.execute('DROP TABLE khataapp_userprofile_old')
        print('Dropped old khataapp_userprofile_old table')
        
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
