import hmac

from fastapi import Cookie, HTTPException, Response
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from .config import get_settings

COOKIE_NAME = "xpg_session"


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(get_settings().secret_key, salt="session")


def check_password(password: str) -> bool:
    return hmac.compare_digest(password.encode(), get_settings().app_password.encode())


def set_session(response: Response) -> None:
    s = get_settings()
    response.set_cookie(COOKIE_NAME, _serializer().dumps({"u": "owner"}), max_age=s.session_max_age_days * 86400,
                        httponly=True, samesite="lax", secure=s.cookie_secure, path="/")


def clear_session(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME, path="/")


def require_user(xpg_session: str | None = Cookie(default=None)) -> str:
    if not xpg_session:
        raise HTTPException(status_code=401, detail="Not signed in")
    try:
        _serializer().loads(xpg_session, max_age=get_settings().session_max_age_days * 86400)
    except (BadSignature, SignatureExpired):
        raise HTTPException(status_code=401, detail="Session expired")
    return "owner"
