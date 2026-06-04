import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'khatapro.settings')
import django
django.setup()

from django.db import connection, transaction

# Disable FK checks, do cleanup, then re-enable
with connection.cursor() as cursor:
    # Disable FK checks
    cursor.execute('PRAGMA foreign_keys = OFF')
    
    try:
        # First, delete OTPs that reference auth_user IDs that don't exist in accounts_user
        cursor.execute('''
            DELETE FROM accounts_otp 
            WHERE user_id NOT IN (SELECT id FROM accounts_user)
        ''')
        print(f"Deleted orphaned OTPs: {cursor.rowcount}")
        
        # Delete related tables first (no FK)
        cursor.execute('DELETE FROM auth_user_groups')
        cursor.execute('DELETE FROM auth_user_user_permissions')
        print('Deleted user groups and permissions')
        
        # Delete auth_user records
        cursor.execute('DELETE FROM auth_user')
        print(f"Deleted auth_user records")
        
        connection.commit()
        
    finally:
        # Re-enable FK checks
        cursor.execute('PRAGMA foreign_keys = ON')
        connection.commit()
        
print("✓ Cleanup complete")
