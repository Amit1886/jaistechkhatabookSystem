class NoCacheStaticMiddleware:
    """
    Desktop builds run offline-first and can be updated by replacing the EXE.

    Browsers/WebView2 may cache static files aggressively, which can cause "old CSS/JS"
    after an update. In desktop mode, prefer correctness over caching.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        path = getattr(request, "path", "") or ""
        if path.startswith("/static/") or path.startswith("/media/"):
            response.headers["Cache-Control"] = "no-store, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"

        return response

