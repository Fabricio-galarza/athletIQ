from .current_user import set_current_user

class CurrentUserMiddleware:
    """
    Middleware that captures the current authenticated user
    and stores it in thread-local storage.

    This allows accessing the user globally (e.g., in signals).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            # Store authenticated user or None
            if request.user.is_authenticated:
                set_current_user(request.user)
            else:
                set_current_user(None)

            response = self.get_response(request)
            return response

        finally:
            # Clean up after request to avoid leaking data between requests
            set_current_user(None)