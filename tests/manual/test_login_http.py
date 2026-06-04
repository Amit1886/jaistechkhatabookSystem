#!/usr/bin/env python
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'khatapro.settings')

import django
django.setup()

from django.test import Client
from django.urls import reverse
from accounts.models import User

# Create a test client
client = Client()

# Test with an actual user
user = User.objects.get(id=1)  
print(f"Testing login for user: {user.username}")
print(f"User ID: {user.id}")
print(f"User mobile: {user.mobile}")

# Try to access the login page
print("\n=== Testing login page ===")
response = client.get('/login/')
print(f"Login page status: {response.status_code}")

# Try to login with the test user
# The login view expects 'identifier' and 'password' or mobile+OTP
print("\n=== Testing login POST ===")
response = client.post('/login/', {
    'username': user.username,
    'password': 'any_password',  # We'll try with dummy password
})
print(f"Login attempt status: {response.status_code}")

# Check if redirected (successful) or still on login page (failed)
if response.status_code == 302:  # Redirect
    print("Login redirected (likely successful)")
    print(f"Redirect location: {response.url}")
elif response.status_code == 200:
    print("Login page shown again (likely failed)")
    if b'User not found' in response.content:
        print("Error: 'User not found' message found")
    elif b'error' in response.content:
        print("Error message found in response")
else:
    print(f"Unexpected status code: {response.status_code}")
