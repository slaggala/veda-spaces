"""Access tokens: JWS ``at+jwt``, ES256 with ``kid`` (05 §5, AUTH-004).

Claims: iss, aud, sub, sid, jti, iat, nbf, exp, av, amr, stp, pwd_change.
No permissions and no PII. Validity is checked against the platform clock so
tests can control time; the session is then checked uncached per request.
"""

from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass
from datetime import datetime

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from veda.config import settings
from veda.kernel import clock
from veda.kernel.ids import new_id

ALGORITHM = "ES256"
LEEWAY_SECONDS = 30


class TokenInvalid(Exception):
    pass


class TokenExpired(Exception):
    def __init__(self, claims: dict):
        super().__init__("expired")
        self.claims = claims


@dataclass(frozen=True)
class _Keys:
    kid: str
    private: ec.EllipticCurvePrivateKey
    verify: dict[str, ec.EllipticCurvePublicKey]


_keys: _Keys | None = None
_keys_source: tuple | None = None


def _load() -> _Keys:
    global _keys, _keys_source
    s = settings()
    source = (s.jwt_private_key_pem, s.jwt_kid, s.jwt_previous_public_key_pem, s.jwt_previous_kid, s.env)
    if _keys is not None and _keys_source == source:
        return _keys
    if s.jwt_private_key_pem:
        private = serialization.load_pem_private_key(s.jwt_private_key_pem.encode(), password=None)
    else:
        if s.is_production:
            raise RuntimeError("VEDA_JWT_PRIVATE_KEY_PEM is required in production")
        seed = int.from_bytes(hashlib.sha256(b"veda-dev-jwt::" + s.env.encode()).digest(), "big")
        private = ec.derive_private_key(seed % (2**255), ec.SECP256R1())
    verify = {s.jwt_kid: private.public_key()}
    if s.jwt_previous_public_key_pem and s.jwt_previous_kid:
        verify[s.jwt_previous_kid] = serialization.load_pem_public_key(s.jwt_previous_public_key_pem.encode())
    _keys = _Keys(s.jwt_kid, private, verify)
    _keys_source = source
    return _keys


def issue(*, user_id: str, session_id: str, authz_version: int, amr: list[str], session_type: str,
          pwd_change: bool = False, ttl_seconds: int | None = None) -> tuple[str, int]:
    keys = _load()
    s = settings()
    now = clock.now()
    ttl = ttl_seconds or int(s.access_token_ttl.total_seconds())
    iat = int(now.timestamp())
    claims = {
        "iss": s.jwt_issuer, "aud": s.jwt_audience, "sub": user_id, "sid": session_id, "jti": new_id(),
        "iat": iat, "nbf": iat, "exp": iat + ttl, "av": authz_version, "amr": amr,
        "stp": "recovery" if session_type == "RECOVERY" else "full",
    }
    if pwd_change:
        claims["pwd_change"] = True
    token = jwt.encode(claims, keys.private, algorithm=ALGORITHM, headers={"kid": keys.kid, "typ": "at+jwt"})
    return token, ttl


def decode(token: str) -> dict:
    """Verify signature, header and claims. Raises TokenExpired with the claims when only ``exp`` failed."""
    keys = _load()
    s = settings()
    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError as exc:
        raise TokenInvalid(str(exc)) from exc
    if header.get("alg") != ALGORITHM or header.get("typ") != "at+jwt":
        raise TokenInvalid("bad header")
    key = keys.verify.get(header.get("kid"))
    if key is None:
        raise TokenInvalid("unknown kid")
    try:
        claims = jwt.decode(
            token, key, algorithms=[ALGORITHM], audience=s.jwt_audience, issuer=s.jwt_issuer,
            options={"verify_exp": False, "verify_nbf": False, "verify_iat": False,
                     "require": ["iss", "aud", "sub", "sid", "jti", "iat", "nbf", "exp", "av", "amr", "stp"]},
        )
    except jwt.PyJWTError as exc:
        raise TokenInvalid(str(exc)) from exc
    now = int(clock.now().timestamp())
    if claims["nbf"] > now + LEEWAY_SECONDS:
        raise TokenInvalid("not yet valid")
    if claims["exp"] <= now:
        raise TokenExpired(claims)
    return claims


def _b64(n: int) -> str:
    return base64.urlsafe_b64encode(n.to_bytes(32, "big")).rstrip(b"=").decode()


def jwks() -> dict:
    keys = _load()
    out = []
    for kid, pub in keys.verify.items():
        nums = pub.public_numbers()
        out.append({"kty": "EC", "crv": "P-256", "kid": kid, "use": "sig", "alg": ALGORITHM,
                    "x": _b64(nums.x), "y": _b64(nums.y)})
    return {"keys": out}


def expires_at(claims: dict) -> datetime:
    return datetime.fromtimestamp(claims["exp"], tz=clock.now().tzinfo)
