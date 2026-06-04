#!/usr/bin/env python
import os
import django
import sys

# Setup Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'khatapro.settings')
sys.path.insert(0, r'C:\Users\hp\Documents\Newfolder\jaistechkhatabookSystem')

django.setup()

from django.core.management import call_command

# Apply migrations
try:
    call_command('migrate', 'accounts', verbosity=2)
    print("✓ Migration applied successfully!")
except Exception as e:
    print(f"✗ Migration failed: {e}")
    sys.exit(1)
