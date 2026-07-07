from django.test import SimpleTestCase

from darts.utils.league_tables import (
    blank_if_default,
    default_stand_html,
    default_uitslagen_html,
    is_default_league_table,
)


class LeagueTableDefaultsTests(SimpleTestCase):
    def test_default_uitslagen_is_recognized(self):
        html = default_uitslagen_html()
        self.assertTrue(is_default_league_table(html, 'uitslagen'))
        self.assertEqual(blank_if_default(html, 'uitslagen'), '')

    def test_default_stand_is_recognized(self):
        html = default_stand_html()
        self.assertTrue(is_default_league_table(html, 'stand'))
        self.assertEqual(blank_if_default(html, 'stand'), '')

    def test_filled_cell_is_not_default(self):
        html = default_uitslagen_html().replace('>&nbsp;</td>', '>3-1</td>', 1)
        self.assertFalse(is_default_league_table(html, 'uitslagen'))

    def test_ckeditor_attributes_still_default(self):
        html = default_stand_html().replace(
            'class="league-table league-table--stand"',
            'class="league-table league-table--stand" border="1"',
        )
        self.assertTrue(is_default_league_table(html, 'stand'))

