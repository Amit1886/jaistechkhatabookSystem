import os
import django
import sys

# Add the project directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'khatapro.settings')
django.setup()

from accounts.models import User

# Promote demouser11@gmail.com to superuser
try:
    user = User.objects.get(email='demouser11@gmail.com')
    user.is_superuser = True
    user.is_staff = True
    user.save()
    print(f"User {user.username} promoted to superuser.")
except User.DoesNotExist:
    print("User with email demouser11@gmail.com not found.")
