import os
import django
import sys

# Add the project directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'khatapro.settings')
django.setup()

from accounts.models import User

# Check all users
users = User.objects.all()
print("All users:")
for user in users:
    print(f"Username: {user.username}, Email: {user.email}, Superuser: {user.is_superuser}, Staff: {user.is_staff}, Active: {user.is_active}")

# Check if there's a superuser
superuser = User.objects.filter(is_superuser=True).first()
if superuser:
    print(f"\nSuperuser found: {superuser.username}")
else:
    print("\nNo superuser found. Creating one...")
    # Create a superuser if none exists
    user = User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
    print(f"Superuser created: {user.username}")
