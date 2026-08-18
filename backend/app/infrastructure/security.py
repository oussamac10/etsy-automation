"""Password hashing, session tokens and credential encryption.

Three primitives, all delegated to maintained libraries. Nothing here invents a
construction: Argon2id comes from ``argon2-cffi``, authenticated encryption from
``cryptography``'s Fernet, and the key derivation from its HKDF.

Nothing in this module logs. A log line at this layer would be a log line next
to a plaintext secret.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

#: OWASP's second recommended Argon2id configuration (19 MiB, t=2, p=1).
_HASHER = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1)

#: A dummy hash to verify against when the account does not exist, so a missing
#: user and a wrong password take the same time. Computed once at import.
_DUMMY_HASH = _HASHER.hash("not-a-real-password-timing-equaliser")

#: Below this, an application key has too little entropy to be worth deriving
#: from. The `.env.example` placeholder is longer, so local development works.
MIN_ENCRYPTION_KEY_LENGTH = 32

#: Domain separation for HKDF, so the same ``ENCRYPTION_KEY`` cannot produce the
#: same subkey for two different purposes.
_CREDENTIAL_INFO = b"etsy-automation/provider-credential/v1"


class EncryptionConfigurationError(RuntimeError):
    """The encryption key is missing, too short or otherwise unusable."""


class CredentialDecryptionError(RuntimeError):
    """A stored credential could not be decrypted with the configured key.

    Almost always a key-version mismatch after a rotation. Deliberately does not
    include the ciphertext.
    """


def hash_password(password: str) -> str:
    """Argon2id hash, including its parameters and salt in the encoded string."""
    if not password:
        raise ValueError("password must not be empty")
    return _HASHER.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    """Constant-work password check.

    ``password_hash`` may be ``None`` for a user row that has no credential yet.
    In that case a dummy verification still runs, so "no such user", "no password
    set" and "wrong password" are indistinguishable by timing as well as by the
    response body.
    """
    candidate = password_hash or _DUMMY_HASH
    try:
        _HASHER.verify(candidate, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False
    return password_hash is not None


def needs_rehash(password_hash: str) -> bool:
    """True when the stored hash uses weaker parameters than the current policy."""
    try:
        return _HASHER.check_needs_rehash(password_hash)
    except InvalidHashError:
        return True


def generate_session_token() -> str:
    """A 256-bit URL-safe session token. Never persisted in this form."""
    return secrets.token_urlsafe(32)


def hash_session_token(token: str) -> str:
    """The stored form of a session token.

    Plain SHA-256 rather than Argon2: the token is already 256 bits of CSPRNG
    output, so there is nothing to brute-force and the lookup happens on every
    request. Storing the digest means a database dump cannot be replayed as a
    session.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def tokens_equal(left: str, right: str) -> bool:
    """Constant-time comparison for CSRF tokens."""
    return hmac.compare_digest(left, right)


def _derive_fernet_key(application_key: str, *, info: bytes) -> bytes:
    """HKDF-SHA256 from the application key to a 32-byte Fernet key.

    ``ENCRYPTION_KEY`` is an operator-supplied string, not necessarily 32 raw
    bytes. Deriving means any sufficiently long value works, and the same value
    always produces the same key, so a restart can still read what it wrote.
    """
    if len(application_key) < MIN_ENCRYPTION_KEY_LENGTH:
        raise EncryptionConfigurationError(
            f"ENCRYPTION_KEY must be at least {MIN_ENCRYPTION_KEY_LENGTH} characters."
        )
    derived = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        # No salt: the key must be reproducible across processes and restarts,
        # and HKDF is defined to be safe with a zero-filled salt.
        salt=None,
        info=info,
    ).derive(application_key.encode("utf-8"))
    return base64.urlsafe_b64encode(derived)


class CredentialCipher:
    """Authenticated encryption for provider credentials at rest.

    Writes always use the current key. Reads accept the current key and, during a
    rotation, one retired key, so existing rows stay readable until
    ``python -m app.rotate_encryption_key`` has re-encrypted them. The version is
    stored beside every ciphertext, so a row written under any other key is
    reported as a configuration error rather than a decryption failure.

    Only one retired key is held at a time: finish a rotation before starting the
    next. See ``docs/authentication-and-secrets.md``.
    """

    def __init__(
        self,
        application_key: str,
        *,
        key_version: int,
        previous_key: str | None = None,
        previous_key_version: int | None = None,
    ) -> None:
        if key_version < 1:
            raise EncryptionConfigurationError("ENCRYPTION_KEY_VERSION must be 1 or greater.")
        if (previous_key is None) != (previous_key_version is None):
            raise EncryptionConfigurationError(
                "a previous key and its version must be supplied together."
            )
        self._fernet = Fernet(_derive_fernet_key(application_key, info=_CREDENTIAL_INFO))
        self.key_version = key_version
        self.previous_key_version = previous_key_version
        self._previous = (
            Fernet(_derive_fernet_key(previous_key, info=_CREDENTIAL_INFO))
            if previous_key is not None
            else None
        )

    def encrypt(self, plaintext: str) -> bytes:
        if not plaintext:
            raise ValueError("refusing to encrypt an empty credential")
        return self._fernet.encrypt(plaintext.encode("utf-8"))

    def decrypt(self, ciphertext: bytes, *, key_version: int) -> str:
        if key_version == self.key_version:
            fernet = self._fernet
        elif self._previous is not None and key_version == self.previous_key_version:
            fernet = self._previous
        else:
            raise CredentialDecryptionError(
                f"credential was encrypted with key version {key_version}; "
                f"the configured key is version {self.key_version}"
            )
        try:
            return fernet.decrypt(ciphertext).decode("utf-8")
        except InvalidToken as exc:
            raise CredentialDecryptionError(
                "credential could not be decrypted with the configured key"
            ) from exc


def mask_secret(plaintext: str, *, visible: int = 4) -> str:
    """The only representation of a credential an API may return.

    Shows the last few characters so the owner can tell which key is stored,
    and nothing else. Short values reveal nothing at all.
    """
    if len(plaintext) <= visible * 2:
        return "•" * 8
    return "•" * 8 + plaintext[-visible:]


ALLOWED_IMAGE_MIMES = {"image/jpeg", "image/png", "image/webp"}


def validate_image_payload(
    content: bytes,
    content_type: str,
    max_bytes: int = 150 * 1024 * 1024,
) -> None:
    """Validate image bytes, MIME type, and decodable header."""
    clean_mime = content_type.lower().strip()
    if clean_mime not in ALLOWED_IMAGE_MIMES:
        raise ValueError(
            f"Unsupported image type '{content_type}'. Allowed: {sorted(ALLOWED_IMAGE_MIMES)}"
        )
    if len(content) == 0:
        raise ValueError("Uploaded image file is empty.")
    if len(content) > max_bytes:
        raise ValueError(
            f"Uploaded image size ({len(content)} bytes) exceeds maximum limit ({max_bytes} bytes)."
        )
    # Validate magic bytes / signatures
    is_jpeg = content.startswith(b"\xff\xd8")
    is_png = content.startswith(b"\x89PNG\r\n\x1a\n")
    is_webp = len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP"
    if not (is_jpeg or is_png or is_webp):
        raise ValueError("Invalid image file format or corrupted binary data.")
