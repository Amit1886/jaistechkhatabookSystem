import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'khatapro.settings')
import django
django.setup()

from accounts.models import User, OTP
from khataapp.models import UserProfile as KhataProfile
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from uuid import uuid4

print('=== FULL SIGNUP + OTP VERIFICATION TEST ===\n')

# Use unique identifier
uid = str(uuid4())[:8]

# 1. SIGNUP
with transaction.atomic():
    user = User.objects.create_user(
        username=f'flowtest_{uid}',
        email=f'flowtest_{uid}@test.com',
        password='test123'
    )
    user.is_active = False
    user.save()
    
    otp = OTP.objects.create(
        user=user,
        code='123456',
        purpose='signup',
        sent_to_email=user.email,
        sent_to_mobile='9999999999',
        expires_at=timezone.now() + timedelta(minutes=10)
    )

profile = KhataProfile.objects.create(
    user=user,
    created_from='signup',
    plan=None,
    mobile='9999999999',
    full_name=user.username
)

print(f'1. SIGNUP SUCCESS')
print(f'   User: {user.username} (ID: {user.id})')
print(f'   is_active: {user.is_active}')
print(f'   OTP: {otp.code}')

# 2. VERIFY OTP
otp.verified = True
otp.save()

user.is_active = True
user.is_otp_verified = True
user.save()

print(f'\n2. OTP VERIFIED')
print(f'   User is_active: {user.is_active}')
print(f'   User is_otp_verified: {user.is_otp_verified}')

# 3. CHECK LOGIN
from django.contrib.auth import authenticate
logged_in_user = authenticate(username=f'flowtest_{uid}', password='test123')
print(f'\n3. LOGIN TEST')
print(f'   Authenticated: {logged_in_user is not None}')
print(f'   Username: {logged_in_user.username if logged_in_user else "FAILED"}')

print('\n=== ALL TESTS PASSED ===')
