"""Password hashing, session tokens and credential encryption.

These are the primitives every security guarantee in Phase 3 rests on, so they
are tested directly rather than only through the API.
"""

from __future__ import annotations

import pytest

from app.infrastructure.security import (
    CredentialCipher,
    CredentialDecryptionError,
    EncryptionConfigurationError,
    generate_session_token,
    hash_password,
    hash_session_token,
    mask_secret,
    needs_rehash,
    tokens_equal,
    verify_password,
)

PASSWORD = "correct horse battery staple"
KEY = "test-encryption-key-not-a-real-key-0123456789"


# --- Passwords -------------------------------------------------------------


def test_hash_is_argon2id_and_never_the_password() -> None:
    hashed = hash_password(PASSWORD)
    assert hashed.startswith("$argon2id$")
    assert PASSWORD not in hashed


def test_the_same_password_hashes_differently_each_time() -> None:
    """A per-hash salt: two owners with the same password have no shared row."""
    assert hash_password(PASSWORD) != hash_password(PASSWORD)


def test_verify_accepts_the_right_password_and_rejects_others() -> None:
    hashed = hash_password(PASSWORD)
    assert verify_password(hashed, PASSWORD) is True
    assert verify_password(hashed, PASSWORD + "!") is False
    assert verify_password(hashed, "") is False


def test_verify_against_no_stored_hash_is_false_not_an_error() -> None:
    """A user row without a password must not authenticate, and must not crash."""
    assert verify_password(None, PASSWORD) is False


def test_verify_survives_a_corrupt_hash() -> None:
    assert verify_password("not-a-hash", PASSWORD) is False


def test_empty_password_cannot_be_hashed() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        hash_password("")


def test_a_current_hash_does_not_need_rehashing() -> None:
    assert needs_rehash(hash_password(PASSWORD)) is False
    # An unreadable hash is treated as needing replacement, not as valid.
    assert needs_rehash("garbage") is True


# --- Session tokens --------------------------------------------------------


def test_session_tokens_are_unique_and_long() -> None:
    tokens = {generate_session_token() for _ in range(50)}
    assert len(tokens) == 50
    assert all(len(token) >= 40 for token in tokens)


def test_token_hash_is_stable_and_hides_the_token() -> None:
    token = generate_session_token()
    digest = hash_session_token(token)
    assert digest == hash_session_token(token)
    assert len(digest) == 64
    assert token not in digest


def test_tokens_equal_compares_values() -> None:
    assert tokens_equal("abc", "abc") is True
    assert tokens_equal("abc", "abd") is False


# --- Credential encryption -------------------------------------------------


def test_round_trip() -> None:
    cipher = CredentialCipher(KEY, key_version=1)
    ciphertext = cipher.encrypt("sk-provider-secret-value")
    assert cipher.decrypt(ciphertext, key_version=1) == "sk-provider-secret-value"


def test_ciphertext_contains_no_plaintext() -> None:
    cipher = CredentialCipher(KEY, key_version=1)
    ciphertext = cipher.encrypt("sk-provider-secret-value")
    assert b"sk-provider-secret-value" not in ciphertext


def test_encryption_is_not_deterministic() -> None:
    """Fernet includes a random IV, so equal secrets are not equal ciphertext."""
    cipher = CredentialCipher(KEY, key_version=1)
    assert cipher.encrypt("same") != cipher.encrypt("same")


def test_the_same_key_decrypts_across_instances() -> None:
    """A restart must still read what the previous process wrote."""
    ciphertext = CredentialCipher(KEY, key_version=1).encrypt("value")
    assert CredentialCipher(KEY, key_version=1).decrypt(ciphertext, key_version=1) == "value"


def test_a_different_key_cannot_decrypt() -> None:
    ciphertext = CredentialCipher(KEY, key_version=1).encrypt("value")
    other = CredentialCipher("a-completely-different-key-0123456789012", key_version=1)
    with pytest.raises(CredentialDecryptionError):
        other.decrypt(ciphertext, key_version=1)


def test_a_key_version_mismatch_is_reported_not_guessed() -> None:
    cipher = CredentialCipher(KEY, key_version=2)
    ciphertext = cipher.encrypt("value")
    with pytest.raises(CredentialDecryptionError, match="key version 1"):
        cipher.decrypt(ciphertext, key_version=1)


def test_tampered_ciphertext_is_rejected() -> None:
    """Fernet is authenticated: a flipped byte fails rather than decrypting."""
    cipher = CredentialCipher(KEY, key_version=1)
    ciphertext = bytearray(cipher.encrypt("value"))
    ciphertext[-1] ^= 0x01
    with pytest.raises(CredentialDecryptionError):
        cipher.decrypt(bytes(ciphertext), key_version=1)


def test_a_short_key_is_refused() -> None:
    with pytest.raises(EncryptionConfigurationError, match="at least 32"):
        CredentialCipher("too-short", key_version=1)


def test_key_version_zero_is_refused() -> None:
    with pytest.raises(EncryptionConfigurationError, match="ENCRYPTION_KEY_VERSION"):
        CredentialCipher(KEY, key_version=0)


def test_empty_credentials_are_not_encrypted() -> None:
    with pytest.raises(ValueError, match="empty credential"):
        CredentialCipher(KEY, key_version=1).encrypt("")


# --- Key rotation ----------------------------------------------------------

OLD_KEY = "the-retired-key-0123456789012345678901"


def _rotating() -> CredentialCipher:
    return CredentialCipher(KEY, key_version=2, previous_key=OLD_KEY, previous_key_version=1)


def test_a_row_written_under_the_retired_key_is_still_readable() -> None:
    """The whole point of rotation: no data loss while both keys are configured."""
    old_ciphertext = CredentialCipher(OLD_KEY, key_version=1).encrypt("sk-old-secret")
    assert _rotating().decrypt(old_ciphertext, key_version=1) == "sk-old-secret"


def test_writes_always_use_the_current_key() -> None:
    cipher = _rotating()
    ciphertext = cipher.encrypt("sk-new-secret")
    assert cipher.decrypt(ciphertext, key_version=2) == "sk-new-secret"
    # The retired key alone cannot read it, which is what makes retirement real.
    with pytest.raises(CredentialDecryptionError):
        CredentialCipher(OLD_KEY, key_version=2).decrypt(ciphertext, key_version=2)


def test_a_third_key_version_is_still_refused() -> None:
    cipher = _rotating()
    with pytest.raises(CredentialDecryptionError, match="key version 5"):
        cipher.decrypt(cipher.encrypt("value"), key_version=5)


def test_the_retired_key_needs_its_version() -> None:
    with pytest.raises(EncryptionConfigurationError, match="together"):
        CredentialCipher(KEY, key_version=2, previous_key=OLD_KEY)
    with pytest.raises(EncryptionConfigurationError, match="together"):
        CredentialCipher(KEY, key_version=2, previous_key_version=1)


# --- Masking ---------------------------------------------------------------


def test_mask_shows_only_a_suffix() -> None:
    masked = mask_secret("sk-live-abcdefgh1234")
    assert masked == "•" * 8 + "1234"
    assert "abcdefgh" not in masked


def test_short_secrets_reveal_nothing() -> None:
    assert mask_secret("short") == "•" * 8
