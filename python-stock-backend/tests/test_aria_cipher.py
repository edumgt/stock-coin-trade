"""ARIA (RFC 5794) 테스트: 표준 벡터, 라운드트립, OpenSSL 교차 검증, API."""

import os
import shutil
import subprocess

import pytest

from app.services.aria_cipher import ARIA, decrypt_text, derive_key, encrypt_text

# RFC 5794 Appendix A test vectors (key, plaintext, ciphertext).
VECTORS = [
    ("000102030405060708090a0b0c0d0e0f", "00112233445566778899aabbccddeeff", "d718fbd6ab644c739da95f3be6451778"),
    ("000102030405060708090a0b0c0d0e0f1011121314151617", "00112233445566778899aabbccddeeff", "26449c1805dbe7aa25a468ce263a9e79"),
    ("000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f", "00112233445566778899aabbccddeeff", "f92bd7c79fb72e2f2b8f80c1972d24fc"),
]


@pytest.mark.parametrize(("key", "plain", "cipher"), VECTORS)
def test_rfc5794_vectors(key, plain, cipher):
    aria = ARIA(bytes.fromhex(key))
    assert aria.encrypt_block(bytes.fromhex(plain)).hex() == cipher
    assert aria.decrypt_block(bytes.fromhex(cipher)).hex() == plain


def test_invalid_key_length():
    with pytest.raises(ValueError):
        ARIA(b"short")


def test_cbc_round_trip_all_sizes():
    for bits in (128, 192, 256):
        key, iv = os.urandom(bits // 8), os.urandom(16)
        for length in (0, 1, 15, 16, 17, 100):
            msg = os.urandom(length)
            assert ARIA(key).decrypt_cbc(ARIA(key).encrypt_cbc(msg, iv), iv) == msg


def test_text_helpers_and_wrong_key():
    key = derive_key("비밀번호", 256)
    token = encrypt_text("한국산 ARIA 알고리즘 ✓", key)
    assert decrypt_text(token, key) == "한국산 ARIA 알고리즘 ✓"
    assert token != encrypt_text("한국산 ARIA 알고리즘 ✓", key), "random IV must change output"
    with pytest.raises((ValueError, UnicodeDecodeError)):
        decrypt_text(token, derive_key("다른키", 256))


@pytest.mark.skipif(not shutil.which("openssl"), reason="openssl not installed")
def test_matches_openssl():
    for bits in (128, 192, 256):
        key, iv, msg = os.urandom(bits // 8), os.urandom(16), os.urandom(37)
        proc = subprocess.run(
            ["openssl", "enc", f"-aria-{bits}-cbc", "-K", key.hex(), "-iv", iv.hex()],
            input=msg, capture_output=True,
        )
        if proc.returncode != 0:
            pytest.skip("openssl build lacks ARIA")
        assert ARIA(key).encrypt_cbc(msg, iv) == proc.stdout


def test_encrypt_decrypt_round_trip(client):
    res = client.post("/api/aria/encrypt", json={"text": "010-1234-5678", "passphrase": "pw", "key_bits": 128})
    body = res.json()
    assert body["ok"] is True, body
    assert body["algorithm"] == "ARIA-128-CBC"
    res = client.post("/api/aria/decrypt", json={"cipher": body["cipher"], "passphrase": "pw", "key_bits": 128})
    assert res.json()["text"] == "010-1234-5678"


def test_server_key_when_passphrase_omitted(client):
    body = client.post("/api/aria/encrypt", json={"text": "hi"}).json()
    assert body["key_source"] == "server"
    assert client.post("/api/aria/decrypt", json={"cipher": body["cipher"]}).json()["text"] == "hi"


def test_validation_errors(client):
    assert client.post("/api/aria/encrypt", json={}).status_code == 400
    assert client.post("/api/aria/encrypt", json={"text": "x", "key_bits": 100}).status_code == 400
    assert client.post("/api/aria/decrypt", json={"cipher": "not base64!!"}).status_code == 400
    wrong = client.post("/api/aria/decrypt", json={"cipher": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=", "passphrase": "x"})
    assert wrong.status_code == 400
    assert wrong.json()["ok"] is False


def test_info_self_test(client):
    body = client.get("/api/aria/info").json()
    assert body["self_test"]["passed"] is True
