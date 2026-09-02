import unittest

from parse_qr import QRParseError, TicketQR, parse_qr


class ParseQrTests(unittest.TestCase):
    def test_legacy_format(self):
        result = parse_qr("participant_id:12345seed:aB3xK9mN2p")
        self.assertEqual(result, TicketQR(participant_id=12345, seed="aB3xK9mN2p"))

    def test_compact_format(self):
        result = parse_qr("12345aB3xK9mN2p")
        self.assertEqual(result, TicketQR(participant_id=12345, seed="aB3xK9mN2p"))

    def test_compact_single_digit_id(self):
        result = parse_qr("1aB3xK9mN2p")
        self.assertEqual(result, TicketQR(participant_id=1, seed="aB3xK9mN2p"))

    def test_compact_long_id(self):
        result = parse_qr("1234567890aB3xK9mN2p")
        self.assertEqual(result, TicketQR(participant_id=1234567890, seed="aB3xK9mN2p"))

    def test_strips_whitespace(self):
        result = parse_qr("  12345aB3xK9mN2p  ")
        self.assertEqual(result, TicketQR(participant_id=12345, seed="aB3xK9mN2p"))

    def test_rejects_empty_input(self):
        with self.assertRaises(QRParseError):
            parse_qr("")

    def test_rejects_none_input(self):
        with self.assertRaises(QRParseError):
            parse_qr(None)

    def test_rejects_too_short_compact(self):
        with self.assertRaises(QRParseError):
            parse_qr("1234567890")

    def test_rejects_non_digit_id_in_compact(self):
        with self.assertRaises(QRParseError):
            parse_qr("abc123aB3xK9mN2p")

    def test_rejects_non_alnum_seed_in_compact(self):
        with self.assertRaises(QRParseError):
            parse_qr("12345aB3xK9-2p")

    def test_rejects_legacy_without_seed(self):
        with self.assertRaises(QRParseError):
            parse_qr("participant_id:12345")

    def test_rejects_legacy_with_empty_seed(self):
        with self.assertRaises(QRParseError):
            parse_qr("participant_id:12345seed:")


if __name__ == "__main__":
    unittest.main()
