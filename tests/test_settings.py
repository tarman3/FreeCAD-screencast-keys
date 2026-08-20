import unittest

from screencast_keys import settings


class SettingsTest(unittest.TestCase):
    def setUp(self):
        self.original_memory = dict(settings._memory)
        settings._memory.clear()

    def tearDown(self):
        settings._memory.clear()
        settings._memory.update(self.original_memory)

    def test_keyboard_side_is_saved_and_loaded(self):
        values = settings.OverlaySettings(keyboard_side="left")
        settings.save(values)

        self.assertEqual(settings.load().keyboard_side, "left")

    def test_invalid_keyboard_side_falls_back_to_left(self):
        settings._memory["KeyboardSide"] = "above"

        self.assertEqual(settings.load().keyboard_side, "left")

    def test_mouse_display_preferences_are_saved_and_loaded(self):
        values = settings.OverlaySettings(
            mouse_display_time=1.75,
            show_mouse_labels=True,
        )
        settings.save(values)

        loaded = settings.load()
        self.assertAlmostEqual(loaded.mouse_display_time, 1.75)
        self.assertTrue(loaded.show_mouse_labels)

    def test_mouse_labels_are_enabled_by_default(self):
        self.assertTrue(settings.load().show_mouse_labels)


if __name__ == "__main__":
    unittest.main()
