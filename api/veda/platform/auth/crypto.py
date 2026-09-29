"""Token hashing, action-token derivation and MFA secret envelope encryption.

* Opaque tokens (refresh, MFA challenge) are 256-bit CSPRNG values; only their
  SHA-256 is stored (05 §6, 03 §5.7).
* Single-use action tokens (reset, invite, enrollment, email) are derived as
  ``base64url(HMAC-SHA-256(K_action, token_row_id ‖ purpose))``. Only the
  SHA-256 of the token is stored, and the outbox worker can re-derive the link
  from the row id without any secret ever entering a table (03 §2.8, SEC-005).
* TOTP seeds are AES-256-GCM encrypted under a KMS-wrapped data key
  (envelope encryption, 03 §5.5, F-13).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
from dataclasses import dataclass

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from veda.config import settings

RECOVERY_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"  # 32 symbols, no 0/O/1/I


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def new_opaque_token() -> str:
    return secrets.token_urlsafe(32)  # 256 bits


def derive_action_token(token_id: str, purpose: str) -> str:
    mac = hmac.new(settings().action_token_key, f"{token_id}:{purpose}".encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(mac).rstrip(b"=").decode()


def recovery_code_hash(code: str) -> str:
    normalized = normalize_recovery_code(code)
    return hmac.new(settings().recovery_code_hmac_key, normalized.encode(), hashlib.sha256).hexdigest()


def normalize_recovery_code(code: str) -> str:
    return "".join(ch for ch in code.upper() if ch.isalnum())


def new_recovery_code() -> str:
    raw = "".join(secrets.choice(RECOVERY_ALPHABET) for _ in range(10))  # 50 bits
    return f"{raw[:5]}-{raw[5:]}"


# --- KMS providers ------------------------------------------------------------


@dataclass(frozen=True)
class DataKey:
    plaintext: bytes
    wrapped_b64: str
    key_arn: str


class LocalKmsProvider:
    """Development/test stand-in for AWS KMS. Wraps data keys with a local AES key."""

    def __init__(self, master_key: bytes, key_arn: str):
        self._aead = AESGCM(hashlib.sha256(master_key).digest())
        self.key_arn = key_arn

    def generate_data_key(self) -> DataKey:
        plaintext = AESGCM.generate_key(bit_length=256)
        nonce = os.urandom(12)
        wrapped = nonce + self._aead.encrypt(nonce, plaintext, self.key_arn.encode())
        return DataKey(plaintext, base64.b64encode(wrapped).decode(), self.key_arn)

    def decrypt_data_key(self, wrapped_b64: str, key_arn: str) -> bytes:
        blob = base64.b64decode(wrapped_b64)
        return self._aead.decrypt(blob[:12], blob[12:], key_arn.encode())


class AwsKmsProvider:  # pragma: no cover - requires AWS
    def __init__(self, key_arn: str, region: str):
        import boto3

        self._client = boto3.client("kms", region_name=region)
        self.key_arn = key_arn

    def generate_data_key(self) -> DataKey:
        resp = self._client.generate_data_key(KeyId=self.key_arn, KeySpec="AES_256")
        return DataKey(resp["Plaintext"], base64.b64encode(resp["CiphertextBlob"]).decode(), resp["KeyId"])

    def decrypt_data_key(self, wrapped_b64: str, key_arn: str) -> bytes:
        resp = self._client.decrypt(CiphertextBlob=base64.b64decode(wrapped_b64), KeyId=key_arn)
        return resp["Plaintext"]


_provider = None


def kms_provider():
    global _provider
    s = settings()
    if _provider is None or getattr(_provider, "key_arn", None) != s.kms_key_arn:
        if s.kms_provider != "aws" and not s.dev_keys_allowed:
            raise RuntimeError(f"the local KMS provider is not available in {s.env} (IR-09)")
        _provider = (
            AwsKmsProvider(s.kms_key_arn, s.aws_region)
            if s.kms_provider == "aws"
            else LocalKmsProvider(s.local_kms_master_key, s.kms_key_arn)
        )
    return _provider


def reset_provider() -> None:
    global _provider
    _provider = None


def encrypt_secret(secret: bytes) -> tuple[str, str, str]:
    """Returns (secret_ciphertext_b64, wrapped_data_key_b64, kms_key_arn)."""
    data_key = kms_provider().generate_data_key()
    nonce = os.urandom(12)
    ciphertext = AESGCM(data_key.plaintext).encrypt(nonce, secret, b"veda-totp-v1")
    return base64.b64encode(nonce + ciphertext).decode(), data_key.wrapped_b64, data_key.key_arn


def decrypt_secret(secret_ciphertext: str, wrapped_data_key: str, kms_key_arn: str) -> bytes:
    plaintext_key = kms_provider().decrypt_data_key(wrapped_data_key, kms_key_arn)
    blob = base64.b64decode(secret_ciphertext)
    return AESGCM(plaintext_key).decrypt(blob[:12], blob[12:], b"veda-totp-v1")
