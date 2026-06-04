from __future__ import annotations

from django.db import models

from whatsapp.crypto import decrypt_str, encrypt_str, is_encrypted


class EncryptedTextField(models.TextField):
    """
    TextField that encrypts at rest using Fernet.

    - Stores encrypted values prefixed with `enc:`
    - Transparently decrypts on read
    - Backward compatible with existing plaintext rows (no prefix)
    """

    def from_db_value(self, value, expression, connection):  # type: ignore[override]
        if value is None:
            return value
        try:
            return decrypt_str(value)
        except Exception:
            return ""

    def to_python(self, value):  # type: ignore[override]
        if value is None:
            return value
        if isinstance(value, str) and is_encrypted(value):
            try:
                return decrypt_str(value)
            except Exception:
                return ""
        return value

    def get_prep_value(self, value):  # type: ignore[override]
        value = super().get_prep_value(value)
        if value is None:
            return value
        try:
            return encrypt_str(value)
        except Exception:
            # Never block DB writes if encryption fails unexpectedly.
            return value

