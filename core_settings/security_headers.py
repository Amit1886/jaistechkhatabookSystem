import os


class SecurityHeadersMiddleware:
    """
    Adds baseline security headers without changing templates.

    Django's SecurityMiddleware covers some headers; this middleware fills gaps and
    keeps everything environment-configurable to avoid breaking existing deployments.
    """

    def __init__(self, get_response):
        self.get_response = get_response

        self.referrer_policy = os.getenv("REFERRER_POLICY", "strict-origin-when-cross-origin")
        self.permissions_policy = os.getenv(
            "PERMISSIONS_POLICY",
            # Default: allow microphone for same-origin so Voice Accounting works out-of-the-box.
            # Deployments can harden this by setting PERMISSIONS_POLICY env var.
            "camera=(), microphone=(self), geolocation=(self), payment=()",
        )
        self.coop = os.getenv("COOP", "same-origin")
        self.corp = os.getenv("CORP", "same-origin")

    def __call__(self, request):
        response = self.get_response(request)

        response.headers.setdefault("Referrer-Policy", self.referrer_policy)
        response.headers.setdefault("Permissions-Policy", self.permissions_policy)
        response.headers.setdefault("Cross-Origin-Opener-Policy", self.coop)
        response.headers.setdefault("Cross-Origin-Resource-Policy", self.corp)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")

        return response
