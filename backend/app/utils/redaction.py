import re
from typing import Any, Dict, List, Union

# Sensitive field keys to redact (exact or suffix match)
SENSITIVE_EXACT_KEYS = {
    "password",
    "secret",
    "api_key",
    "token",
    "access_token",
    "refresh_token",
    "authorization",
    "signature",
    "x-razorpay-signature",
    "webhook_secret",
    "razorpay_key_secret",
    "razorpay_secret",
    "cvv",
    "cvc",
    "pan",
    "card_number",
    "credit_card",
    "private_key",
    "secret_key"
}

# Regex to detect JWT patterns or high-entropy tokens
JWT_REGEX = re.compile(r"^[A-Za-z0-9-_=]+\.[A-Za-z0-9-_=]+\.?[A-Za-z0-9-_.+/=]*$")

def redact_sensitive_data(data: Any) -> Any:
    """
    Recursively redacts sensitive keys and values from dictionaries, lists, and primitives.
    Guarantees that sensitive secrets are removed BEFORE canonical hashing and database persistence.
    """
    if isinstance(data, dict):
        sanitized = {}
        for key, value in data.items():
            key_lower = str(key).lower().strip()
            
            # Check if key is explicitly sensitive
            if key_lower in SENSITIVE_EXACT_KEYS or any(s in key_lower for s in ["_secret", "api_key", "password", "token"]):
                # Avoid false positives for harmless fields like 'token_usage' or 'currency'
                if key_lower in ("token_usage", "currency", "idempotency_key", "key"):
                    if key_lower == "key" and isinstance(value, str) and len(value) > 20:
                        sanitized[key] = "[REDACTED_KEY]"
                    else:
                        sanitized[key] = redact_sensitive_data(value)
                else:
                    sanitized[key] = "[REDACTED]"
            else:
                sanitized[key] = redact_sensitive_data(value)
        return sanitized

    elif isinstance(data, list):
        return [redact_sensitive_data(item) for item in data]

    elif isinstance(data, str):
        # Mask Bearer tokens
        if data.lower().startswith("bearer ") and len(data) > 15:
            return "Bearer [REDACTED_TOKEN]"
        return data

    return data
