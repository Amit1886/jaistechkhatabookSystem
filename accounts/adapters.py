from allauth.core.exceptions import ImmediateHttpResponse
from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from accounts.models import OTP
from django.shortcuts import redirect
from django.urls import reverse
from django.contrib.auth import login as django_login


class OTPAccountAdapter(DefaultAccountAdapter):

    def login(self, request, user):
        # Only allow login if OTP verified
        if user.is_active:
            django_login(request, user)

    def save_user(self, request, user, form=None):
        user = super().save_user(request, user, form)

        # Inactivate until OTP verified
        user.is_active = False
        user.save(update_fields=["is_active"])

        OTP.create_for(
            user=user,
            purpose="signup",
            email=user.email,
            mobile=getattr(user, "mobile", None)
        )

        request.session["otp_user_id"] = user.id
        request.session["otp_purpose"] = "signup"

        return user


class OTPSocialAdapter(DefaultSocialAccountAdapter):

    def save_user(self, request, sociallogin, form=None):
        """
        This is where Google user is ACTUALLY saved to DB
        """
        user = super().save_user(request, sociallogin, form)

        # Mark as inactive until OTP verified
        user.is_active = False
        user.is_social_login = True
        user.save(update_fields=["is_active", "is_social_login"])

        OTP.create_for(
            user=user,
            purpose="signup",
            email=user.email
        )

        request.session["otp_user_id"] = user.id
        request.session["otp_purpose"] = "signup"

        # Redirect to OTP page
        raise ImmediateHttpResponse(
            redirect(reverse("verify_otp"))
        )
