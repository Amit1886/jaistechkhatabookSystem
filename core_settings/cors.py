class LocalDevCORSMiddleware:
    """
    Allow the Flutter web dev server to call Django APIs during local testing.
    Supports Chrome DevTools, Flutter web, and mobile debugging ports.

    This is intentionally narrow and package-free: production domains can still
    be controlled by the normal deployment/proxy layer.
    """

    allowed_origins = {
        # Flutter web dev servers
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:5175",
        "http://127.0.0.1:5175",
        "http://localhost:5176",
        "http://127.0.0.1:5176",
        # Chrome Flutter web default ports
        "http://localhost:53785",
        "http://127.0.0.1:53785",
        "http://localhost:8888",
        "http://127.0.0.1:8888",
        # Local network development
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        # Allow any local IP for development
        "http://localhost",
        "http://127.0.0.1",
    }
    
    @staticmethod
    def is_allowed_origin(origin: str) -> bool:
        """Check if origin is in allowed list or is local IP based."""
        if not origin:
            return False
        origin_lower = origin.lower()
        # Direct match
        if origin_lower in LocalDevCORSMiddleware.allowed_origins:
            return True
        # Allow localhost variations
        if any(origin_lower.startswith(base) for base in ["http://localhost", "http://127.0.0.1", "http://localhost:"]):
            return True
        return False

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        origin = request.headers.get("Origin", "")
        if request.method == "OPTIONS" and self.is_allowed_origin(origin):
            from django.http import HttpResponse
            response = HttpResponse()
        else:
            response = self.get_response(request)

        if self.is_allowed_origin(origin):
            response["Access-Control-Allow-Origin"] = origin
            response["Vary"] = "Origin"
            response["Access-Control-Allow-Credentials"] = "true"
            response["Access-Control-Allow-Headers"] = "authorization, content-type, x-requested-with"
            response["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
        return response
