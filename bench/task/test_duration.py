"""Test suite for the duration module. Do not modify this file."""

import unittest

from duration import parse_duration, format_duration


class TestParseBasics(unittest.TestCase):
    def test_seconds(self):
        self.assertEqual(parse_duration("PT30S"), 30)

    def test_minutes(self):
        self.assertEqual(parse_duration("PT1M"), 60)

    def test_hours(self):
        self.assertEqual(parse_duration("PT2H"), 7200)

    def test_days(self):
        self.assertEqual(parse_duration("P1D"), 86400)

    def test_combined(self):
        self.assertEqual(parse_duration("P1DT2H30M"), 95400)


class TestMonthVersusMinute(unittest.TestCase):
    """'M' means months before the T separator and minutes after it."""

    def test_months_before_t(self):
        self.assertEqual(parse_duration("P1M"), 30 * 86400)

    def test_minutes_after_t(self):
        self.assertEqual(parse_duration("PT1M"), 60)

    def test_years(self):
        self.assertEqual(parse_duration("P1Y"), 365 * 86400)


class TestWeeks(unittest.TestCase):
    def test_single_week(self):
        self.assertEqual(parse_duration("P1W"), 7 * 86400)

    def test_multiple_weeks(self):
        self.assertEqual(parse_duration("P2W"), 14 * 86400)


class TestFractional(unittest.TestCase):
    def test_fractional_seconds(self):
        self.assertAlmostEqual(parse_duration("PT1.5S"), 1.5)

    def test_fractional_hours(self):
        self.assertAlmostEqual(parse_duration("PT0.5H"), 1800)


class TestNegative(unittest.TestCase):
    def test_negative_seconds(self):
        self.assertEqual(parse_duration("-PT30S"), -30)

    def test_negative_combined(self):
        self.assertEqual(parse_duration("-P1DT2H30M"), -95400)


class TestErrors(unittest.TestCase):
    def test_garbage(self):
        with self.assertRaises(ValueError):
            parse_duration("not a duration")

    def test_empty(self):
        with self.assertRaises(ValueError):
            parse_duration("")

    def test_none(self):
        with self.assertRaises(ValueError):
            parse_duration(None)


class TestFormat(unittest.TestCase):
    def test_format_simple(self):
        self.assertEqual(format_duration(90), "PT1M30S")

    def test_format_zero(self):
        self.assertEqual(format_duration(0), "PT0S")

    def test_format_negative(self):
        self.assertEqual(format_duration(-90), "-PT1M30S")

    def test_round_trip(self):
        for value in (0, 30, 90, 3600, 86400, 95400):
            self.assertEqual(parse_duration(format_duration(value)), value)

    def test_round_trip_negative(self):
        self.assertEqual(parse_duration(format_duration(-95400)), -95400)


if __name__ == "__main__":
    unittest.main(verbosity=2)
