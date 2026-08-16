import unittest

from screencast_keys.model import EventHistory


class EventHistoryTest(unittest.TestCase):
    def setUp(self):
        self.now = 10.0
        self.history = EventHistory(3, 2.0, lambda: self.now)

    def test_repeats_are_combined(self):
        self.history.add("Tab")
        self.history.add("Tab")
        self.assertEqual(len(self.history.events), 1)
        self.assertEqual(self.history.events[0].display_text(), "Tab ×2")

    def test_history_is_bounded(self):
        for label in ("A", "B", "C", "D"):
            self.history.add(label)
        self.assertEqual([event.label for event in self.history.events], ["B", "C", "D"])

    def test_events_expire(self):
        self.history.add("A")
        self.now = 12.1
        self.assertTrue(self.history.expire())
        self.assertEqual(self.history.events, [])

    def test_fades_at_end(self):
        event = self.history.add("A")
        self.now = 11.75
        self.assertAlmostEqual(self.history.opacity(event), 0.5)

    def test_event_can_override_display_duration(self):
        event = self.history.add("LMB", duration=0.5)

        self.assertAlmostEqual(event.expires - event.created, 0.5)
        self.assertAlmostEqual(event.duration, 0.5)


if __name__ == "__main__":
    unittest.main()
