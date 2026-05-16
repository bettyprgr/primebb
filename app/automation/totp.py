import pyotp


def current_totp(secret: str) -> str:
    clean = secret.replace(" ", "").strip()
    return pyotp.TOTP(clean).now()
