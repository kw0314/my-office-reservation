from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from types import SimpleNamespace

from django.test import SimpleTestCase
from django.utils import timezone

from . import services


class SeriesRepeatUntilTests(SimpleTestCase):
    def test_apply_series_repeat_until_cancels_future_instances(self):
        tz = ZoneInfo("America/Chicago")
        base = timezone.make_aware(datetime(2026, 7, 1, 9, 0), tz)

        before = SimpleNamespace(start_at=base, status=services.Reservation.STATUS_CONFIRMED, series_repeat_until=None)
        on_day = SimpleNamespace(start_at=base + timedelta(days=2), status=services.Reservation.STATUS_CONFIRMED, series_repeat_until=None)
        after = SimpleNamespace(start_at=base + timedelta(days=4), status=services.Reservation.STATUS_CONFIRMED, series_repeat_until=None)

        items = [before, on_day, after]
        services._apply_series_repeat_until(items, repeat_until=date(2026, 7, 3))

        self.assertEqual(before.status, services.Reservation.STATUS_CONFIRMED)
        self.assertEqual(on_day.status, services.Reservation.STATUS_CONFIRMED)
        self.assertEqual(after.status, services.Reservation.STATUS_CANCELLED)
        self.assertEqual(before.series_repeat_until, date(2026, 7, 3))


class RepeatDateGenerationTests(SimpleTestCase):
    def test_monthly_custom_fifth_week_requires_actual_fifth_weekday(self):
        dates = services._generate_repeat_dates(
            start_date=date(2026, 2, 1),
            repeat_until=date(2026, 3, 31),
            repeat_type="monthly_custom",
            repeat_days=[2],  # Tuesday
            repeat_weeks_of_month=[5],
        )

        self.assertEqual(dates, [date(2026, 3, 31)])
