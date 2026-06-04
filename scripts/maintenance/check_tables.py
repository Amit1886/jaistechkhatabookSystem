import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'khatapro.settings')
import django
django.setup()

from django.db import connection

with connection.cursor() as cursor:
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = cursor.fetchall()

print('All tables:')
for table in tables:
    if 'auth_user' in table[0] or 'accounts_user' in table[0]:
        print(f'  >>> {table[0]} <<<')
    else:
        print(f'  {table[0]}')
