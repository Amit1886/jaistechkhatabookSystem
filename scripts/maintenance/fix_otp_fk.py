import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'khatapro.settings')
import django
django.setup()

from django.db import connection

# Disable FK checks, drop and recreate OTP table
with connection.cursor() as cursor:
    # Disable FK checks
    cursor.execute('PRAGMA foreign_keys = OFF')
    
    try:
        # Rename old OTP table
        cursor.execute('ALTER TABLE accounts_otp RENAME TO accounts_otp_old')
        print('Renamed accounts_otp to accounts_otp_old')
        
        # Create new OTP table with correct FK
        cursor.execute('''
            CREATE TABLE accounts_otp (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code VARCHAR(6) NOT NULL,
                purpose VARCHAR(20) NOT NULL,
                sent_to_email VARCHAR(254),
                sent_to_mobile VARCHAR(15),
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                expires_at DATETIME NOT NULL,
                verified BOOLEAN NOT NULL DEFAULT FALSE,
                resend_count INTEGER UNSIGNED NOT NULL DEFAULT 0,
                user_id INTEGER NOT NULL,
                FOREIGN KEY (user_id) REFERENCES accounts_user(id) ON DELETE CASCADE
            )
        ''')
        print('Created new accounts_otp table with correct FK')
        
        # Copy data from old table
        cursor.execute('''
            INSERT INTO accounts_otp 
            SELECT * FROM accounts_otp_old
        ''')
        print(f'Migrated OTP records')
        
        # Drop old table
        cursor.execute('DROP TABLE accounts_otp_old')
        print('Dropped old accounts_otp_old table')
        
        connection.commit()
        
    except Exception as e:
        print(f'Error: {e}')
        connection.rollback()
    finally:
        # Re-enable FK checks
        cursor.execute('PRAGMA foreign_keys = ON')
        connection.commit()
