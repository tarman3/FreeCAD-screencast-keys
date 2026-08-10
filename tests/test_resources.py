import unittest
from pathlib import Path
from xml.etree import ElementTree


class ResourceTest(unittest.TestCase):
    def test_preferences_category_icon_uses_freecad_name(self):
        root = Path(__file__).resolve().parents[1]
        icon = root / "Resources" / "icons" / "preferences-screencast_keys.svg"

        self.assertTrue(icon.is_file())
        ElementTree.parse(icon)


if __name__ == "__main__":
    unittest.main()
