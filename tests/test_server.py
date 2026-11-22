import json
import unittest
from unittest.mock import patch, MagicMock
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
    get_disk_space,
    get_top_processes,
    set_timer,
    get_timer_status,
    cancel_timer,
    get_network_diagnostics,
    empty_recycle_bin,
    create_desktop_folder,
    get_volume,
    get_system_uptime,
    clear_notes,
    clipboard_clear,
    flip_coin,
    roll_dice,
    random_number,
    APP_MAP,
    switch_to_window,
    universal_launch,
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

    def test_disk_space_intent(self):
        result = route_intent("how much storage do I have")
        self.assertIsNotNone(result)
        self.assertEqual(result.get("action"), "disk_space")
        self.assertIn("free_gb", result)

    def test_top_processes_intent(self):
        result = route_intent("what is using my ram")
        self.assertIsNotNone(result)
        self.assertEqual(result.get("action"), "top_processes")
        self.assertIn("processes", result)

    def test_timer_lifecycle_intent(self):
        # Set timer
        set_res = route_intent("set a timer for 10 minutes")
        self.assertIsNotNone(set_res)
        self.assertEqual(set_res.get("action"), "timer")
        self.assertEqual(set_res.get("duration"), 600)

        # Status
        status_res = route_intent("check timer")
        self.assertIsNotNone(status_res)
        self.assertEqual(status_res.get("action"), "timer")
        self.assertGreater(status_res.get("remaining", 0), 0)

        # Cancel
        cancel_res = route_intent("cancel timer")
        self.assertIsNotNone(cancel_res)
        self.assertEqual(cancel_res.get("action"), "timer")

    def test_ip_diagnostics_intent(self):
        result = route_intent("what is my ip")
        self.assertIsNotNone(result)
        self.assertEqual(result.get("action"), "network_diagnostics")
        self.assertIn("local_ip", result)

    def test_volume_query_intent(self):
        result = route_intent("what is the volume")
        self.assertIsNotNone(result)
        self.assertEqual(result.get("action"), "get_volume")
        self.assertIn("level", result)

    def test_uptime_intent(self):
        result = route_intent("system uptime")
        self.assertIsNotNone(result)
        self.assertEqual(result.get("action"), "uptime")
        self.assertIn("uptime_seconds", result)
        self.assertIn("boot_time", result)

    def test_clear_notes_intent(self):
        result = route_intent("clear notes")
        self.assertIsNotNone(result)
        self.assertEqual(result.get("action"), "note")
        self.assertEqual(result.get("status"), "ok")

    def test_clear_clipboard_intent(self):
        result = route_intent("clear clipboard")
        self.assertIsNotNone(result)
        self.assertEqual(result.get("action"), "clipboard")

    def test_random_utilities_intents(self):
        # Coin flip
        c = route_intent("flip a coin")
        self.assertIsNotNone(c)
        self.assertEqual(c.get("action"), "coin")
        self.assertIn(c.get("result"), ["Heads", "Tails"])

        # Dice roll
        d = route_intent("roll a d20")
        self.assertIsNotNone(d)
        self.assertEqual(d.get("action"), "dice")
        self.assertEqual(d.get("sides"), 20)
        self.assertTrue(1 <= d.get("result") <= 20)

        # Random number
        rn = route_intent("pick a number between 10 and 20")
        self.assertIsNotNone(rn)
        self.assertEqual(rn.get("action"), "random_number")
        self.assertTrue(10 <= rn.get("result") <= 20)


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

    def test_get_disk_space(self):
        res = get_disk_space()
        self.assertEqual(res.get("status"), "ok")
        self.assertIn("total_gb", res)
        self.assertIn("free_gb", res)
        self.assertGreater(res.get("total_gb", 0), 0)

    def test_get_top_processes(self):
        res = get_top_processes(3)
        self.assertEqual(res.get("status"), "ok")
        self.assertIn("processes", res)
        self.assertIsInstance(res.get("processes"), list)

    def test_timer_functions(self):
        # Set
        s = set_timer(120, "study")
        self.assertEqual(s.get("action"), "timer")
        self.assertEqual(s.get("duration"), 120)

        # Status
        st = get_timer_status()
        self.assertEqual(st.get("action"), "timer")
        self.assertGreater(st.get("remaining", 0), 0)

        # Cancel
        c = cancel_timer()
        self.assertEqual(c.get("action"), "timer")

    def test_get_network_diagnostics(self):
        diag = get_network_diagnostics()
        self.assertEqual(diag.get("status"), "ok")
        self.assertIn("local_ip", diag)
        self.assertIn("hostname", diag)

    def test_get_volume_helper(self):
        res = get_volume()
        self.assertIn(res.get("status"), ["ok", "error"])
        if res.get("status") == "ok":
            self.assertIn("level", res)
            self.assertIn("muted", res)

    def test_get_system_uptime_helper(self):
        res = get_system_uptime()
        self.assertEqual(res.get("status"), "ok")
        self.assertIn("uptime_seconds", res)
        self.assertIn("uptime_human", res)
        self.assertIn("boot_time", res)
        self.assertGreaterEqual(res.get("uptime_seconds", -1), 0)

    def test_clear_notes_helper(self):
        res = clear_notes()
        self.assertEqual(res.get("status"), "ok")
        self.assertIn("cleared", res.get("reply", "").lower())

    def test_clear_clipboard_helper(self):
        res = clipboard_clear()
        self.assertIn(res.get("status"), ["ok", "error"])

    def test_random_utility_helpers(self):
        # Coin
        c = flip_coin()
        self.assertEqual(c.get("status"), "ok")
        self.assertIn(c.get("result"), ["Heads", "Tails"])

        # Dice
        d = roll_dice(6)
        self.assertEqual(d.get("status"), "ok")
        self.assertTrue(1 <= d.get("result") <= 6)

        # Random number
        rn = random_number(5, 10)
        self.assertEqual(rn.get("status"), "ok")
        self.assertTrue(5 <= rn.get("result") <= 10)


class TestCipherCrossPlatform(unittest.TestCase):
    def test_app_map_cross_platform_completeness(self):
        for app_name, os_dict in APP_MAP.items():
            for os_target in ["Windows", "Darwin", "Linux"]:
                self.assertIn(os_target, os_dict, f"Missing {os_target} launcher for {app_name}")
                self.assertTrue(bool(os_dict[os_target]), f"Empty {os_target} launcher command for {app_name}")

    def test_disk_space_cross_platform(self):
        with patch("server.OS", "Darwin"):
            d_res = get_disk_space()
            self.assertEqual(d_res.get("status"), "ok")
            self.assertEqual(d_res.get("path"), "/")

        with patch("server.OS", "Linux"):
            l_res = get_disk_space()
            self.assertEqual(l_res.get("status"), "ok")
            self.assertEqual(l_res.get("path"), "/")

    def test_empty_recycle_bin_cross_platform(self):
        with patch("server.OS", "Darwin"), patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            res = empty_recycle_bin()
            self.assertEqual(res.get("status"), "ok")
            self.assertIn("trash", res.get("reply", "").lower())

        with patch("server.OS", "Linux"), patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            res = empty_recycle_bin()
            self.assertEqual(res.get("status"), "ok")
            self.assertIn("trash", res.get("reply", "").lower())

    def test_switch_window_cross_platform(self):
        with patch("server.OS", "Darwin"), patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            res = switch_to_window("Spotify")
            self.assertEqual(res.get("status"), "ok")

        with patch("server.OS", "Linux"), patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            res = switch_to_window("Terminal")
            self.assertEqual(res.get("status"), "ok")

    def test_universal_launch_cross_platform(self):
        with patch("server.OS", "Darwin"), patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            res = universal_launch("Xcode")
            self.assertEqual(res.get("status"), "ok")

        with patch("server.OS", "Linux"), patch("shutil.which", return_value="/usr/bin/gimp"), patch("subprocess.Popen"):
            res = universal_launch("gimp")
            self.assertEqual(res.get("status"), "ok")

    def test_get_volume_cross_platform(self):
        with patch("server.OS", "Darwin"), patch("subprocess.check_output", side_effect=["65", "false"]):
            res = get_volume()
            self.assertEqual(res.get("status"), "ok")
            self.assertEqual(res.get("level"), 65)
            self.assertFalse(res.get("muted"))

        with patch("server.OS", "Linux"), patch("subprocess.check_output", return_value="Simple mixer control 'Master',0\nFront Left: Playback 45 [70%] [on]"):
            res = get_volume()
            self.assertEqual(res.get("status"), "ok")
            self.assertEqual(res.get("level"), 70)
            self.assertFalse(res.get("muted"))


if __name__ == "__main__":
    unittest.main()
