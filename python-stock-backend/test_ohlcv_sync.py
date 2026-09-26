import unittest
from datetime import date

from ohlcv_sync import plan_year_ranges


class OhlcvYearPlanTest(unittest.TestCase):
    def test_missing_years_and_current_increment_are_planned(self):
        existing = {
            2024: {"last_date": date(2024, 12, 30), "row_count": 240},
            2026: {"last_date": date(2026, 9, 23), "row_count": 180},
        }
        ranges = plan_year_ranges(existing, 2024, date(2026, 9, 26), correction_days=7)
        self.assertEqual(ranges, [
            (2025, date(2025, 1, 1), date(2026, 1, 1)),
            (2026, date(2026, 9, 16), date(2026, 9, 27)),
        ])

    def test_reconciliation_plans_every_year(self):
        existing = {2025: {"last_date": date(2025, 12, 30), "row_count": 240}}
        ranges = plan_year_ranges(existing, 2025, date(2026, 2, 3), reconcile=True)
        self.assertEqual(ranges, [
            (2025, date(2025, 1, 1), date(2026, 1, 1)),
            (2026, date(2026, 1, 1), date(2026, 2, 4)),
        ])


if __name__ == "__main__":
    unittest.main()
