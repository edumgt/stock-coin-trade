"""ARIA (RFC 5794) tests: standard vectors, round trips, OpenSSL cross-check, API."""

import os
import shutil
import subprocess
import unittest

from flask import Flask

from aria_api import aria_bp
from aria_cipher import ARIA, decrypt_text, derive_key, encrypt_text

# RFC 5794 Appendix A test vectors (key, plaintext, ciphertext).
VECTORS = [
    ("000102030405060708090a0b0c0d0e0f", "00112233445566778899aabbccddeeff", "d718fbd6ab644c739da95f3be6451778"),
    ("000102030405060708090a0b0c0d0e0f1011121314151617", "00112233445566778899aabbccddeeff", "26449c1805dbe7aa25a468ce263a9e79"),
    ("000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f", "00112233445566778899aabbccddeeff", "f92bd7c79fb72e2f2b8f80c1972d24fc"),
]


class AriaBlockTests(unittest.TestCase):
    def test_rfc5794_vectors(self):
        for key, plain, cipher in VECTORS:
            with self.subTest(bits=len(key) * 4):
                aria = ARIA(bytes.fromhex(key))
                self.assertEqual(aria.encrypt_block(bytes.fromhex(plain)).hex(), cipher)
                self.assertEqual(aria.decrypt_block(bytes.fromhex(cipher)).hex(), plain)

    def test_invalid_key_length(self):
        with self.assertRaises(ValueError):
            ARIA(b"short")

    def test_cbc_round_trip_all_sizes(self):
        for bits in (128, 192, 256):
            key, iv = os.urandom(bits // 8), os.urandom(16)
            for length in (0, 1, 15, 16, 17, 100):
                msg = os.urandom(length)
                self.assertEqual(ARIA(key).decrypt_cbc(ARIA(key).encrypt_cbc(msg, iv), iv), msg)

    def test_text_helpers_and_wrong_key(self):
        key = derive_key("비밀번호", 256)
        token = encrypt_text("한국산 ARIA 알고리즘 ✓", key)
        self.assertEqual(decrypt_text(token, key), "한국산 ARIA 알고리즘 ✓")
        self.assertNotEqual(token, encrypt_text("한국산 ARIA 알고리즘 ✓", key), "random IV must change output")
        with self.assertRaises((ValueError, UnicodeDecodeError)):
            decrypt_text(token, derive_key("다른키", 256))

    @unittest.skipUnless(shutil.which("openssl"), "openssl not installed")
    def test_matches_openssl(self):
        for bits in (128, 192, 256):
            key, iv, msg = os.urandom(bits // 8), os.urandom(16), os.urandom(37)
            proc = subprocess.run(
                ["openssl", "enc", f"-aria-{bits}-cbc", "-K", key.hex(), "-iv", iv.hex()],
                input=msg, capture_output=True,
            )
            if proc.returncode != 0:
                self.skipTest("openssl build lacks ARIA")
            self.assertEqual(ARIA(key).encrypt_cbc(msg, iv), proc.stdout)


class AriaApiTests(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.register_blueprint(aria_bp)
        self.client = app.test_client()

    def test_encrypt_decrypt_round_trip(self):
        res = self.client.post("/api/aria/encrypt", json={"text": "010-1234-5678", "passphrase": "pw", "key_bits": 128})
        body = res.get_json()
        self.assertTrue(body["ok"], body)
        self.assertEqual(body["algorithm"], "ARIA-128-CBC")
        res = self.client.post("/api/aria/decrypt", json={"cipher": body["cipher"], "passphrase": "pw", "key_bits": 128})
        self.assertEqual(res.get_json()["text"], "010-1234-5678")

    def test_server_key_when_passphrase_omitted(self):
        body = self.client.post("/api/aria/encrypt", json={"text": "hi"}).get_json()
        self.assertEqual(body["key_source"], "server")
        self.assertEqual(self.client.post("/api/aria/decrypt", json={"cipher": body["cipher"]}).get_json()["text"], "hi")

    def test_validation_errors(self):
        self.assertEqual(self.client.post("/api/aria/encrypt", json={}).status_code, 400)
        self.assertEqual(self.client.post("/api/aria/encrypt", json={"text": "x", "key_bits": 100}).status_code, 400)
        self.assertEqual(self.client.post("/api/aria/decrypt", json={"cipher": "not base64!!"}).status_code, 400)
        wrong = self.client.post("/api/aria/decrypt", json={"cipher": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=", "passphrase": "x"})
        self.assertEqual(wrong.status_code, 400)
        self.assertFalse(wrong.get_json()["ok"])

    def test_info_self_test(self):
        body = self.client.get("/api/aria/info").get_json()
        self.assertTrue(body["self_test"]["passed"])


if __name__ == "__main__":
    unittest.main()
