class ValidationError(Exception):
    pass


class PayloadValidator:
    def require(self, payload, *fields):
        missing = [field for field in fields if payload.get(field) in (None, "")]
        if missing:
            raise ValidationError(f"Missing required fields: {', '.join(missing)}")
        return True

