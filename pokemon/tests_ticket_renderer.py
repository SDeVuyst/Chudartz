from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase
from django.utils import timezone

from chudartz.ticket_renderer import (
    TEXT_COLUMN_WIDTH,
    _format_access_period,
    _wrap_text,
)
from darts.templatetags import dutch_date


class TicketRendererTests(SimpleTestCase):
    def test_format_access_period_uses_ticket_times(self):
        event_start = timezone.make_aware(datetime(2026, 7, 15, 10, 0))
        event_end = timezone.make_aware(datetime(2026, 7, 15, 18, 0))
        ticket_start = timezone.make_aware(datetime(2026, 7, 15, 9, 0))

        ticket = SimpleNamespace(
            get_toegang_start=lambda: ticket_start,
            get_toegang_einde=lambda: event_end,
        )

        formatted = _format_access_period(ticket)
        self.assertIn("09:00", formatted)
        self.assertIn("18:00", formatted)

    def test_format_access_period_falls_back_to_event_times(self):
        event_start = timezone.make_aware(datetime(2026, 7, 15, 10, 0))
        event_end = timezone.make_aware(datetime(2026, 7, 15, 18, 0))

        ticket = SimpleNamespace(
            get_toegang_start=lambda: event_start,
            get_toegang_einde=lambda: event_end,
        )

        formatted = _format_access_period(ticket)
        self.assertEqual(
            formatted,
            f"{dutch_date.dutch_datetime(event_start)} - {dutch_date.dutch_time(event_end)}",
        )

    @patch("chudartz.ticket_renderer._string_width")
    def test_wrap_text_respects_max_lines(self, mock_string_width):
        mock_string_width.side_effect = lambda text, *_args: len(text)

        lines = _wrap_text("aa bb cc dd ee", "Outfit-Regular", 13, 3, 2)

        self.assertEqual(len(lines), 2)
        self.assertTrue(lines[-1].endswith("..."))

    @patch("chudartz.ticket_renderer._string_width")
    def test_wrap_text_keeps_short_values_on_one_line(self, mock_string_width):
        mock_string_width.side_effect = lambda text, *_args: len(text) * 6

        lines = _wrap_text("Short title", "Outfit-Regular", 13, TEXT_COLUMN_WIDTH, 2)

        self.assertEqual(lines, ["Short title"])
