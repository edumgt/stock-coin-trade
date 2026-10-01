"""한국 표준 블록암호 ARIA 데모 REST API.

POST /api/aria/encrypt  {text, passphrase?, key_bits?}  -> {ok, cipher, ...}
POST /api/aria/decrypt  {cipher, passphrase?, key_bits?} -> {ok, text, ...}
GET  /api/aria/info                                        -> 알고리즘 정보 + 자체 점검
"""

from __future__ import annotations

from fastapi import APIRouter, Body
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.services.aria_cipher import ARIA, decrypt_text, derive_key, encrypt_text

from ..schemas import AriaDecryptBody, AriaEncryptBody

router = APIRouter(prefix="/api/aria", tags=["aria"])

_MAX_TEXT = 10_000
_MAX_CIPHER = 40_000
_RFC_KEY = bytes.fromhex("000102030405060708090a0b0c0d0e0f")
_RFC_PLAIN = bytes.fromhex("00112233445566778899aabbccddeeff")
_RFC_CIPHER = "d718fbd6ab644c739da95f3be6451778"


class AriaRequestError(ValueError):
    pass


def _key_bits(raw) -> int:
    try:
        bits = int(raw)
    except (TypeError, ValueError) as exc:
        raise AriaRequestError("key_bits는 128, 192, 256 중 하나여야 합니다.") from exc
    if bits not in (128, 192, 256):
        raise AriaRequestError("key_bits는 128, 192, 256 중 하나여야 합니다.")
    return bits


def _resolve_key(passphrase, key_bits) -> tuple[bytes, int, str]:
    bits = _key_bits(key_bits)
    if passphrase is not None and not isinstance(passphrase, str):
        raise AriaRequestError("passphrase는 문자열이어야 합니다.")
    if passphrase:
        return derive_key(passphrase, bits), bits, "passphrase"
    server = get_settings().aria_demo_key or "stock-coin-trade-aria-demo-key"
    return derive_key(server, bits), bits, "server"


def _run(build):
    try:
        return {"ok": True, **build()}
    except (AriaRequestError, ValueError, UnicodeDecodeError) as exc:
        message = str(exc) if isinstance(exc, AriaRequestError | ValueError) else "복호화 결과가 UTF-8 문자열이 아닙니다. 키를 확인하세요."
        return JSONResponse({"ok": False, "message": message}, status_code=400)


@router.post("/encrypt")
def encrypt(payload: AriaEncryptBody = Body(default_factory=AriaEncryptBody)):
    def build():
        text = payload.text
        if not isinstance(text, str) or text == "":
            raise AriaRequestError("암호화할 text가 필요합니다.")
        if len(text) > _MAX_TEXT:
            raise AriaRequestError(f"text는 최대 {_MAX_TEXT:,}자까지 지원합니다.")
        key, bits, source = _resolve_key(payload.passphrase, payload.key_bits)
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


@router.post("/decrypt")
def decrypt(payload: AriaDecryptBody = Body(default_factory=AriaDecryptBody)):
    def build():
        cipher = payload.cipher
        if not isinstance(cipher, str) or not cipher.strip():
            raise AriaRequestError("복호화할 cipher(base64)가 필요합니다.")
        if len(cipher) > _MAX_CIPHER:
            raise AriaRequestError("cipher가 너무 깁니다.")
        key, bits, source = _resolve_key(payload.passphrase, payload.key_bits)
        return {"algorithm": f"ARIA-{bits}-CBC", "key_bits": bits, "key_source": source, "text": decrypt_text(cipher.strip(), key)}

    return _run(build)


@router.get("/info")
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
            "server_key_configured": bool(get_settings().aria_demo_key),
        }

    return _run(build)
