import threading

# Thread-local storage (one per request/thread)
_user = threading.local()


def set_current_user(user):
    """
    Store the current authenticated user in thread-local storage.
    """
    _user.value = user


def get_current_user():
    """
    Retrieve the current authenticated user.
    Returns None if no user is set.
    """
    return getattr(_user, "value", None)