"""
Automated tests for the Smart Agriculture Dashboard.
Each test runs against its own temporary SQLite database, so the real
data is never touched.

Run:  python -m unittest -v
"""

import os
import sqlite3
import tempfile
import unittest

from app import create_app


class BaseTestCase(unittest.TestCase):
    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.app = create_app(self.db_path)
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    def tearDown(self):
        os.remove(self.db_path)

    def register(self, username="farmer", password="secret123"):
        return self.client.post("/register",
                                data={"username": username, "password": password})

    def login(self, username="farmer", password="secret123"):
        return self.client.post("/login",
                                data={"username": username, "password": password})

    def register_and_login(self):
        self.register()
        self.login()

    @staticmethod
    def reading(**overrides):
        data = {"device_id": "esp32-1", "soil_moisture": 45.5,
                "temperature": 28.2, "light": 31000}
        data.update(overrides)
        return data


class AuthTests(BaseTestCase):
    def test_01_dashboard_redirects_when_logged_out(self):
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/login", resp.headers["Location"])

    def test_02_register_then_login_succeeds(self):
        self.assertEqual(self.register().status_code, 302)
        resp = self.login()
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(self.client.get("/").status_code, 200)

    def test_03_wrong_password_rejected(self):
        self.register()
        resp = self.login(password="wrong-password")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Invalid username or password", resp.data)
        self.assertEqual(self.client.get("/").status_code, 302)

    def test_04_duplicate_username_rejected(self):
        self.register()
        resp = self.register()
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"already taken", resp.data)

    def test_05_password_is_stored_hashed(self):
        self.register(password="secret123")
        with sqlite3.connect(self.db_path) as conn:
            stored = conn.execute("SELECT password_hash FROM users").fetchone()[0]
        self.assertNotEqual(stored, "secret123")
        self.assertNotIn("secret123", stored)

    def test_06_logout_ends_session(self):
        self.register_and_login()
        self.client.get("/logout")
        resp = self.client.get("/api/latest")
        self.assertEqual(resp.status_code, 401)


class ApiAccessTests(BaseTestCase):
    def test_07_all_api_routes_require_login(self):
        for method, path in [("get", "/api/readings"),
                             ("get", "/api/latest"),
                             ("post", "/api/readings")]:
            resp = getattr(self.client, method)(path)
            self.assertEqual(resp.status_code, 401, f"{method.upper()} {path}")


class ValidationTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.register_and_login()

    def test_08_missing_device_id_rejected(self):
        data = self.reading()
        del data["device_id"]
        resp = self.client.post("/api/readings", json=data)
        self.assertEqual(resp.status_code, 400)

    def test_09_non_numeric_value_rejected(self):
        resp = self.client.post("/api/readings",
                                json=self.reading(temperature="hot"))
        self.assertEqual(resp.status_code, 400)

    def test_10_out_of_range_value_rejected(self):
        resp = self.client.post("/api/readings",
                                json=self.reading(soil_moisture=150))
        self.assertEqual(resp.status_code, 400)

    def test_11_non_json_body_rejected(self):
        resp = self.client.post("/api/readings", data="not json")
        self.assertEqual(resp.status_code, 400)


class DataIntegrityTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.register_and_login()

    def test_12_valid_reading_is_stored_and_returned(self):
        resp = self.client.post("/api/readings", json=self.reading())
        self.assertEqual(resp.status_code, 201)
        rows = self.client.get("/api/readings").get_json()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["device_id"], "esp32-1")
        self.assertAlmostEqual(rows[0]["soil_moisture"], 45.5)

    def test_13_latest_returns_newest_reading_per_device(self):
        self.client.post("/api/readings", json=self.reading(temperature=20))
        self.client.post("/api/readings", json=self.reading(temperature=25))
        self.client.post("/api/readings",
                         json=self.reading(device_id="esp32-2", temperature=30))
        latest = self.client.get("/api/latest").get_json()
        by_device = {r["device_id"]: r for r in latest}
        self.assertEqual(set(by_device), {"esp32-1", "esp32-2"})
        self.assertAlmostEqual(by_device["esp32-1"]["temperature"], 25)


if __name__ == "__main__":
    unittest.main()
