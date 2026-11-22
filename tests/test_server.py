import json
import unittest
from pathlib import Path
import sys

# Ensure root directory is on sys.path
ROOT_DIR = Path(__file__).parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from server import (
    app,
    route_intent,
    check_internet_connection,
    safe_eval_math,
    is_offline_error,
)


class TestCipherServer(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_health_endpoint(self):
        res = self.client.get("/health")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data.get("status"), "ok")
        self.assertEqual(data.get("app"), "CIPHER")
        self.assertEqual(data.get("version"), "2.5")
        self.assertIn("os", data)

    def test_root_redirect(self):
        res = self.client.get("/")
        self.assertEqual(res.status_code, 302)
        self.assertTrue(res.headers.get("Location", "").endswith("/app"))

    def test_legacy_cipher_redirect(self):
        res = self.client.get("/cipher.html")
        self.assertEqual(res.status_code, 302)
        self.assertTrue(res.headers.get("Location", "").endswith("/app"))

    def test_serve_app_page(self):
        res = self.client.get("/app")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"CIPHER", res.data)

    def test_serve_landing_page(self):
        res = self.client.get("/landing")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"CIPHER", res.data)

    def test_serve_logo(self):
        res = self.client.get("/cipher_logo.png")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.content_type, "image/png")

    def test_sysinfo_endpoint(self):
        res = self.client.get("/sysinfo")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("os", data)
        self.assertIn("time", data)
        self.assertIn("date", data)

    def test_sysstats_endpoint(self):
        res = self.client.get("/sysstats")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("cpu", data)
        self.assertIn("ram_percent", data)
        self.assertIn("battery", data)

    def test_chat_empty_message(self):
        res = self.client.post("/chat", json={"message": ""})
        self.assertEqual(res.status_code, 400)

    def test_chat_reset(self):
        res = self.client.post("/reset")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("cleared", data.get("status", "").lower())

    def test_traps_crud(self):
        test_trap_name = "__ci_test_trap__"
        # 1. Create or save trap
        res = self.client.post(
            "/traps",
            json={"name": test_trap_name, "apps": ["notepad"], "sites": ["github"]},
        )
        self.assertEqual(res.status_code, 200)

        # 2. Verify list contains trap
        res = self.client.get("/traps")
        self.assertEqual(res.status_code, 200)
        traps = res.get_json()
        self.assertIn(test_trap_name, traps)

        # 3. Delete trap
        res = self.client.delete(f"/traps/{test_trap_name}")
        self.assertEqual(res.status_code, 200)

        # 4. Verify trap removed
        res = self.client.get("/traps")
        self.assertNotIn(test_trap_name, res.get_json())


class TestCipherIntents(unittest.TestCase):
    def test_time_intent(self):
        result = route_intent("what time is it")
        self.assertIsNotNone(result)
        self.assertEqual(result.get("action"), "time")

    def test_date_intent(self):
        result = route_intent("what is today's date")
        self.assertIsNotNone(result)
        self.assertEqual(result.get("action"), "date")

    def test_help_intent(self):
        result = route_intent("help")
        self.assertIsNotNone(result)
        self.assertEqual(result.get("action"), "help")
        self.assertIn("commands", result.get("reply", "").lower())

    def test_greeting_intent(self):
        result = route_intent("hello")
        self.assertIsNotNone(result)
        self.assertEqual(result.get("action"), "greeting")

    def test_sleep_intent(self):
        result = route_intent("cipher sleep")
        self.assertIsNotNone(result)
        self.assertEqual(result.get("action"), "sleep")

    def test_open_website_intent(self):
        result = route_intent("open youtube")
        self.assertIsNotNone(result)
        self.assertEqual(result.get("action"), "open_website")
        self.assertIn("youtube.com", result.get("url", ""))

    def test_search_intent(self):
        result = route_intent("search for machine learning")
        self.assertIsNotNone(result)
        self.assertEqual(result.get("action"), "open_website")
        self.assertIn("google.com/search", result.get("url", ""))

    def test_math_intent(self):
        result = route_intent("calculate 25 * 4")
        self.assertIsNotNone(result)
        self.assertEqual(result.get("action"), "calculator")
        self.assertIn("100", result.get("reply", ""))

    def test_network_status_intent(self):
        result = route_intent("check internet")
        self.assertIsNotNone(result)
        self.assertEqual(result.get("action"), "network_status")
        self.assertIn("status", result)


class TestCipherOfflineHelpers(unittest.TestCase):
    def test_check_internet_connection(self):
        res = check_internet_connection(timeout=0.5)
        self.assertIsInstance(res, bool)

    def test_safe_eval_math_operations(self):
        self.assertEqual(safe_eval_math("25 * 4"), 100)
        self.assertEqual(safe_eval_math("(12 + 8) * 3"), 60)
        self.assertEqual(safe_eval_math("150 / 2"), 75.0)
        self.assertEqual(safe_eval_math("10 - 4 + 2"), 8)

    def test_safe_eval_math_rejects_unsafe(self):
        with self.assertRaises(Exception):
            safe_eval_math("__import__('os').system('dir')")

    def test_is_offline_error(self):
        self.assertTrue(is_offline_error(Exception("Failed to resolve host")))
        self.assertTrue(is_offline_error(Exception("Network is unreachable")))
        self.assertTrue(is_offline_error(Exception("getaddrinfo failed")))
        self.assertFalse(is_offline_error(Exception("Invalid API key")))


if __name__ == "__main__":
    unittest.main()
