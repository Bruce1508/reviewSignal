"""Operator session tokens (`docs/api-spec.md` §15).

The MVP has one user and no role system, so a session carries no identity: it only
proves that the operator password was presented, and when the proof expires. That
makes an HMAC over an expiry timestamp sufficient and keeps sessions out of the
database, where they would be state with no reader.

Rotating `SESSION_SECRET` invalidates every outstanding session, which is the only
revocation mechanism a stateless token can offer.
"""

import hmac
from datetime import UTC, datetime, timedelta
from hashlib import sha256

SESSION_COOKIE = "rs_session"
SESSION_TTL = timedelta(hours=12)


def _sign(secret: str, payload: str) -> str:
    return hmac.new(secret.encode(), payload.encode(), sha256).hexdigest()


def issue_token(secret: str, *, ttl: timedelta = SESSION_TTL, now: datetime | None = None) -> str:
    expires_at = int(((now or datetime.now(UTC)) + ttl).timestamp())
    return f"{expires_at}.{_sign(secret, str(expires_at))}"


def verify_token(secret: str, token: str, *, now: datetime | None = None) -> bool:
    payload, _, signature = token.partition(".")
    if not payload or not signature:
        return False
    # Signature first: an unparsable payload must not be distinguishable by timing
    # from a forged one, and a valid signature is what makes the payload trustworthy.
    if not hmac.compare_digest(signature, _sign(secret, payload)):
        return False
    try:
        expires_at = int(payload)
    except ValueError:
        return False
    return (now or datetime.now(UTC)).timestamp() < expires_at


def password_matches(supplied: str, configured: str) -> bool:
    """An unconfigured password authenticates nobody, including a caller sending ""."""
    if not configured:
        return False
    return hmac.compare_digest(supplied.encode(), configured.encode())
