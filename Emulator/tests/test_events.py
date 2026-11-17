"""Season events (native/events.py): modes, date windows, the content flags they add at login, GM command."""
import datetime
import unittest

from dcemu.native import context, events, version

D = datetime.date


class EventsTest(unittest.TestCase):
    def setUp(self):
        self.saved = context.__dict__.copy()
        version.configure({'version': '2016'})
        context.events = {}

    def tearDown(self):
        context.__dict__.clear()
        context.__dict__.update(self.saved)

    def test_auto_windows_including_the_year_end(self):
        self.assertTrue(events.is_on('christmas', D(2026, 12, 24)))
        self.assertTrue(events.is_on('christmas', D(2027, 1, 3)))
        self.assertFalse(events.is_on('christmas', D(2026, 11, 14)))
        self.assertTrue(events.is_on('halloween', D(2026, 10, 31)))
        self.assertFalse(events.is_on('anniversary', D(2026, 10, 31)))     # no window: off unless on

    def test_easter_follows_easter_sunday(self):
        self.assertEqual(events.easter_sunday(2027), D(2027, 3, 28))
        self.assertEqual(events.easter_sunday(2026), D(2026, 4, 5))
        self.assertTrue(events.is_on('easter', D(2027, 3, 20)))
        self.assertFalse(events.is_on('easter', D(2027, 4, 20)))

    def test_modes_and_custom_dates_from_the_ini(self):
        events.load({'christmas': 'off', 'harvest': 'on', 'summer.dates': '06-01..06-30', 'bogus': 'on',
                     'valentine': 'maybe'})
        self.assertFalse(events.is_on('christmas', D(2026, 12, 24)))
        self.assertTrue(events.is_on('harvest', D(2026, 3, 1)))
        self.assertTrue(events.is_on('summer', D(2026, 6, 15)))
        self.assertFalse(events.is_on('summer', D(2026, 7, 15)))
        self.assertEqual(events.mode('valentine'), 'auto')                 # a bad value stays auto

    def test_flags_of_running_events_only(self):
        f = events.flags(D(2026, 12, 24))
        self.assertEqual(f.get('Etc.EventChristmasTree'), 1)
        self.assertNotIn('Etc.EventHalloween', f)
        self.assertEqual(events.flags(D(2026, 2, 14)).get('Etc.EventValentainChocolate'), 1)   # 2016 flag
        version.configure({'version': '2011'})
        self.assertNotIn('Etc.EventValentainChocolate', events.flags(D(2026, 2, 14)))   # not in the 2011 table

    def test_gm_command(self):
        self.assertIn('christmas', events.gm_command([]))
        self.assertIn('ON', events.gm_command(['anniversary', 'on']))
        self.assertTrue(events.is_on('anniversary'))
        self.assertIn('usage', events.gm_command(['christmas', 'later']))
