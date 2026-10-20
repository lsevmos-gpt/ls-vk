"""Offline tests for safe read-only Meta token expiry checks."""
import unittest
from datetime import datetime, timezone, timedelta

from scripts.meta_ig_token_health import days_until, inspect_metadata


NOW = datetime(2026, 10, 20, 15, 0, tzinfo=timezone.utc)


class TokenHealthTests(unittest.TestCase):
    def test_no_fixed_expiry(self):
        info, alert = inspect_metadata(
            {"is_valid": True, "type": "PAGE", "expires_at": 0, "data_access_expires_at": 0},
            now=NOW)
        self.assertFalse(alert)
        self.assertIn("no_fixed_date_reported", info)
        self.assertNotIn("access_token", info)

    def test_soon_expiring_fails(self):
        expire = int((NOW + timedelta(days=3)).timestamp())
        info, alert = inspect_metadata(
            {"is_valid": True, "type": "PAGE", "expires_at": expire},
            now=NOW)
        self.assertTrue(alert)
        self.assertIn("EXPIRES_IN_DAYS=3.0", info)

    def test_data_access_expiring_warns(self):
        expire = int((NOW + timedelta(days=5)).timestamp())
        _, alert = inspect_metadata(
            {"is_valid": True, "type": "PAGE", "expires_at": 0, "data_access_expires_at": expire},
            now=NOW)
        self.assertTrue(alert)

    def test_invalid_token_fails(self):
        info, alert = inspect_metadata({"is_valid": False, "type": "PAGE"}, now=NOW)
        self.assertTrue(alert)
        self.assertEqual(info, "TOKEN_VALID=false")

    def test_day_count_and_bad_expiry(self):
        self.assertIsNone(days_until(None, NOW))
        self.assertIsNone(days_until(0, NOW))
        self.assertIsNone(days_until("0", NOW))
        with self.assertRaises(ValueError):
            days_until("garbage", NOW)


if __name__ == "__main__":
    unittest.main()
