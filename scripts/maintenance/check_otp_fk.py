import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'khatapro.settings')
import django
django.setup()

from django.db import connection

with connection.cursor() as cursor:
    # Check OTP table schema
    cursor.execute("PRAGMA table_info(accounts_otp)")
    columns = cursor.fetchall()
    print("OTP Table Columns:")
    for col in columns:
        print(f"  {col}")
    
    print("\nForeign Keys on OTP:")
    cursor.execute("PRAGMA foreign_key_list(accounts_otp)")
    fks = cursor.fetchall()
    for fk in fks:
        print(f"  {fk}")
