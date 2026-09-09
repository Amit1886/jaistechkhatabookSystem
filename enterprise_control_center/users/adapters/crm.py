from typing import Any, Dict


def adapt_user(user) -> Dict[str, Any]:
    return {
        "id": user.pk,
        "username": user.username,
        "email": user.email,
    }
