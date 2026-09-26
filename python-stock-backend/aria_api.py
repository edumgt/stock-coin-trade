"""Demo REST API for the Korean ARIA block cipher (see ``aria_cipher``).

POST /api/aria/encrypt  {text, passphrase?, key_bits?}  -> {ok, cipher, ...}
POST /api/aria/decrypt  {cipher, passphrase?, key_bits?} -> {ok, text, ...}
GET  /api/aria/info                                        -> algorithm facts + self-test

Key source: a passphrase supplied by the caller (SHA-256 derived) or, when
omitted, the server-side ``ARIA_DEMO_KEY`` environment value. Production keys
belong in a secret store such as AWS Secrets Manager, not in request bodies.
"""

from __future__ import annotations

import os

from flask import Blueprint, jsonify, request

from aria_cipher import ARIA, decrypt_text, derive_key, encrypt_text

aria_bp = Blueprint("aria", __name__, url_prefix="/api/aria")

_MAX_TEXT = 10_000
_MAX_CIPHER = 40_000
_DEFAULT_KEY_BITS = 256
_RFC_KEY = bytes.fromhex("000102030405060708090a0b0c0d0e0f")
_RFC_PLAIN = bytes.fromhex("00112233445566778899aabbccddeeff")
_RFC_CIPHER = "d718fbd6ab644c739da95f3be6451778"


class AriaRequestError(ValueError):
    pass


def _payload() -> dict:
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise AriaRequestError("JSON 본문이 필요합니다.")
    return data


def _key_bits(data: dict) -> int:
    raw = data.get("key_bits", _DEFAULT_KEY_BITS)
    try:
        bits = int(raw)
    except (TypeError, ValueError) as exc:
        raise AriaRequestError("key_bits는 128, 192, 256 중 하나여야 합니다.") from exc
    if bits not in (128, 192, 256):
        raise AriaRequestError("key_bits는 128, 192, 256 중 하나여야 합니다.")
    return bits


def _resolve_key(data: dict) -> tuple[bytes, int, str]:
    bits = _key_bits(data)
    passphrase = data.get("passphrase")
    if passphrase is not None and not isinstance(passphrase, str):
        raise AriaRequestError("passphrase는 문자열이어야 합니다.")
    if passphrase:
        return derive_key(passphrase, bits), bits, "passphrase"
    server = os.environ.get("ARIA_DEMO_KEY") or "stock-coin-trade-aria-demo-key"
    return derive_key(server, bits), bits, "server"


def _run(build):
    try:
        return jsonify({"ok": True, **build()})
    except (AriaRequestError, ValueError, UnicodeDecodeError) as exc:
        message = str(exc) if isinstance(exc, (AriaRequestError, ValueError)) else "복호화 결과가 UTF-8 문자열이 아닙니다. 키를 확인하세요."
        return jsonify({"ok": False, "message": message}), 400


@aria_bp.post("/encrypt")
def encrypt():
    def build():
        data = _payload()
        text = data.get("text")
        if not isinstance(text, str) or text == "":
            raise AriaRequestError("암호화할 text가 필요합니다.")
        if len(text) > _MAX_TEXT:
            raise AriaRequestError(f"text는 최대 {_MAX_TEXT:,}자까지 지원합니다.")
        key, bits, source = _resolve_key(data)
        cipher = encrypt_text(text, key)
        return {
            "algorithm": f"ARIA-{bits}-CBC",
            "padding": "PKCS#7",
            "encoding": "base64(IV || ciphertext)",
            "key_bits": bits,
            "key_source": source,
            "cipher": cipher,
            "cipher_length": len(cipher),
        }

    return _run(build)


@aria_bp.post("/decrypt")
def decrypt():
    def build():
        data = _payload()
        cipher = data.get("cipher")
        if not isinstance(cipher, str) or not cipher.strip():
            raise AriaRequestError("복호화할 cipher(base64)가 필요합니다.")
        if len(cipher) > _MAX_CIPHER:
            raise AriaRequestError("cipher가 너무 깁니다.")
        key, bits, source = _resolve_key(data)
        text = decrypt_text(cipher.strip(), key)
        return {"algorithm": f"ARIA-{bits}-CBC", "key_bits": bits, "key_source": source, "text": text}

    return _run(build)


@aria_bp.get("/info")
def info():
    def build():
        actual = ARIA(_RFC_KEY).encrypt_block(_RFC_PLAIN).hex()
        return {
            "algorithm": "ARIA",
            "standard": ["KS X 1213-1 (한국 국가표준)", "RFC 5794", "ISO/IEC 18033-3"],
            "block_bits": 128,
            "key_bits": [128, 192, 256],
            "rounds": {"128": 12, "192": 14, "256": 16},
            "mode": "CBC + PKCS#7, IV 16바이트 랜덤",
            "self_test": {
                "key": _RFC_KEY.hex(),
                "plaintext": _RFC_PLAIN.hex(),
                "expected": _RFC_CIPHER,
                "actual": actual,
                "passed": actual == _RFC_CIPHER,
            },
            "server_key_configured": bool(os.environ.get("ARIA_DEMO_KEY")),
        }

    return _run(build)
