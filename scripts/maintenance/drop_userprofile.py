import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'khatapro.settings')
import django
django.setup()

from django.db import connection
import sqlite3

# Disable FK checks, drop and recreate khataapp_userprofile table with ALL columns
with connection.cursor() as cursor:
    # Disable FK checks
    cursor.execute('PRAGMA foreign_keys = OFF')
    
    try:
        # Drop the table (will be recreated by Django migration)
        cursor.execute('DROP TABLE IF EXISTS khataapp_userprofile')
        print('Dropped khataapp_userprofile table')
        
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
