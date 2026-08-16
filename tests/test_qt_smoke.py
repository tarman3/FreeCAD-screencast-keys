import os
import math
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from screencast_keys.controller import ScreencastController
from screencast_keys.qt import QtCore, QtGui, QtWidgets, event_type, qt_value


class QtSmokeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def setUp(self):
        self.window = QtWidgets.QMainWindow()
        self.target = QtWidgets.QWidget()
        self.window.setCentralWidget(self.target)
        self.window.resize(800, 600)
        self.window.show()
        self.controller = ScreencastController(self.window, self.app)
        self.controller.set_enabled(True)
        self.app.processEvents()

    def tearDown(self):
        self.controller.shutdown()
        self.window.close()
        self.app.processEvents()

    def test_controller_is_discoverable_from_main_window(self):
        found = self.window.findChild(QtCore.QObject, "ScreencastKeys")

        self.assertIs(found, self.controller)

    def test_key_and_mouse_are_observed_without_consuming(self):
        key = QtGui.QKeyEvent(
            event_type("KeyPress"),
            qt_value("Key_S", "Key"),
            qt_value("ControlModifier", "KeyboardModifier"),
            "s",
        )
        QtWidgets.QApplication.sendEvent(self.target, key)
        press = QtGui.QMouseEvent(
            event_type("MouseButtonPress"),
            QtCore.QPointF(5, 5),
            QtCore.QPointF(5, 5),
            QtCore.QPointF(5, 5),
            qt_value("LeftButton", "MouseButton"),
            qt_value("LeftButton", "MouseButton"),
            qt_value("NoModifier", "KeyboardModifier"),
        )
        QtWidgets.QApplication.sendEvent(self.target, press)
        self.assertEqual(self.controller.history.events[0].label, "Ctrl + S")
        self.assertEqual(len(self.controller.history.events), 1)
        self.assertIn("left", self.controller.overlay.pressed_buttons)
        self.assertTrue(self.controller.overlay.isVisible())

    def test_propagated_mouse_event_is_counted_once(self):
        def mouse_press(timestamp):
            event = QtGui.QMouseEvent(
                event_type("MouseButtonPress"),
                QtCore.QPointF(5, 5),
                QtCore.QPointF(5, 5),
                QtCore.QPointF(5, 5),
                qt_value("LeftButton", "MouseButton"),
                qt_value("LeftButton", "MouseButton"),
                qt_value("NoModifier", "KeyboardModifier"),
            )
            if hasattr(event, "setTimestamp"):
                event.setTimestamp(timestamp)
            return event

        # FreeCAD can deliver two copies with different native timestamps.
        self.controller.eventFilter(self.target, mouse_press(100))
        release = QtGui.QMouseEvent(
            event_type("MouseButtonRelease"),
            QtCore.QPointF(5, 5),
            QtCore.QPointF(5, 5),
            QtCore.QPointF(5, 5),
            qt_value("LeftButton", "MouseButton"),
            qt_value("NoButton", "MouseButton"),
            qt_value("NoModifier", "KeyboardModifier"),
        )
        self.controller.eventFilter(self.target, release)
        self.controller.eventFilter(self.target, mouse_press(101))
        self.assertEqual(self.controller.history.events, [])

    def test_propagated_key_event_is_counted_once(self):
        def space_event(kind, timestamp):
            event = QtGui.QKeyEvent(
                kind,
                qt_value("Key_Space", "Key"),
                qt_value("NoModifier", "KeyboardModifier"),
                " ",
            )
            if hasattr(event, "setTimestamp"):
                event.setTimestamp(timestamp)
            return event

        self.controller.eventFilter(self.target, space_event(event_type("KeyPress"), 100))
        self.controller.eventFilter(self.target, space_event(event_type("KeyRelease"), 100))
        self.controller.eventFilter(self.target, space_event(event_type("KeyPress"), 101))
        self.controller.eventFilter(self.target, space_event(event_type("KeyRelease"), 101))
        self.assertEqual(len(self.controller.history.events), 1)
        self.assertEqual(self.controller.history.events[0].label, "Space")
        self.assertEqual(self.controller.history.events[0].count, 1)

    def test_shortcut_override_records_held_modifier_chord(self):
        control = qt_value("ControlModifier", "KeyboardModifier")
        no_modifier = qt_value("NoModifier", "KeyboardModifier")
        control_key = qt_value("Key_Control", "Key")
        c_key = qt_value("Key_C", "Key")

        self.controller.eventFilter(
            self.target,
            QtGui.QKeyEvent(event_type("KeyPress"), control_key, control, ""),
        )
        self.assertEqual(
            [event.label for event in self.controller.history.events],
            ["Ctrl"],
        )
        self.assertTrue(math.isinf(self.controller.history.events[0].expires))

        self.controller.eventFilter(
            self.target,
            QtGui.QKeyEvent(event_type("ShortcutOverride"), c_key, control, "c"),
        )
        # A subsequent KeyPress for the same physical key must not add it twice.
        self.controller.eventFilter(
            self.target,
            QtGui.QKeyEvent(event_type("KeyPress"), c_key, control, "c"),
        )
        self.controller.eventFilter(
            self.target,
            QtGui.QShortcutEvent(QtGui.QKeySequence("Ctrl+C"), 1, False),
        )
        self.assertTrue(math.isinf(self.controller.history.events[0].expires))
        self.controller.eventFilter(
            self.target,
            QtGui.QKeyEvent(event_type("KeyRelease"), c_key, control, "c"),
        )
        self.controller.eventFilter(
            self.target,
            QtGui.QKeyEvent(event_type("KeyRelease"), control_key, no_modifier, ""),
        )

        self.assertEqual(
            [event.label for event in self.controller.history.events],
            ["Ctrl + C"],
        )
        self.assertEqual(self.controller.history.events[0].count, 1)
        self.assertFalse(math.isinf(self.controller.history.events[0].expires))

    def test_held_modifier_does_not_expire_until_release(self):
        control = qt_value("ControlModifier", "KeyboardModifier")
        no_modifier = qt_value("NoModifier", "KeyboardModifier")
        control_key = qt_value("Key_Control", "Key")

        self.controller.eventFilter(
            self.target,
            QtGui.QKeyEvent(event_type("KeyPress"), control_key, control, ""),
        )
        event = self.controller.history.events[0]
        self.assertEqual(event.label, "Ctrl")
        self.assertTrue(math.isinf(event.expires))
        self.assertFalse(self.controller.history.expire(self.controller.history.now() + 3600))

        self.controller.eventFilter(
            self.target,
            QtGui.QKeyEvent(event_type("KeyRelease"), control_key, no_modifier, ""),
        )
        self.assertFalse(math.isinf(event.expires))
        self.assertGreater(event.expires, self.controller.history.now())

    def test_multistep_shortcut_is_displayed_as_one_chord(self):
        no_modifier = qt_value("NoModifier", "KeyboardModifier")
        k_key = qt_value("Key_K", "Key")

        # Qt may deliver the shortcut prefix as a normal key before consuming
        # the final key and emitting QShortcutEvent.
        self.controller.eventFilter(
            self.target,
            QtGui.QKeyEvent(event_type("KeyPress"), k_key, no_modifier, "k"),
        )
        self.controller.eventFilter(
            self.target,
            QtGui.QKeyEvent(event_type("KeyRelease"), k_key, no_modifier, "k"),
        )
        self.controller.eventFilter(
            self.target,
            QtGui.QShortcutEvent(QtGui.QKeySequence("K, O"), 2, False),
        )

        self.assertEqual(
            [event.label for event in self.controller.history.events],
            ["K + O"],
        )

    def test_modifier_is_not_applied_after_release(self):
        control = qt_value("ControlModifier", "KeyboardModifier")
        no_modifier = qt_value("NoModifier", "KeyboardModifier")
        control_key = qt_value("Key_Control", "Key")
        v_key = qt_value("Key_V", "Key")

        self.controller.eventFilter(
            self.target,
            QtGui.QKeyEvent(event_type("KeyPress"), control_key, control, ""),
        )
        self.controller.eventFilter(
            self.target,
            QtGui.QKeyEvent(event_type("KeyRelease"), control_key, no_modifier, ""),
        )
        self.controller.eventFilter(
            self.target,
            QtGui.QKeyEvent(event_type("KeyPress"), v_key, no_modifier, "v"),
        )

        self.assertEqual(
            [event.label for event in self.controller.history.events],
            ["Ctrl", "V"],
        )

    def test_password_input_is_redacted(self):
        field = QtWidgets.QLineEdit(self.target)
        field.setEchoMode(QtWidgets.QLineEdit.Password)
        key = QtGui.QKeyEvent(
            event_type("KeyPress"),
            qt_value("Key_A", "Key"),
            qt_value("NoModifier", "KeyboardModifier"),
            "a",
        )
        QtWidgets.QApplication.sendEvent(field, key)
        QtWidgets.QApplication.sendEvent(field, key)
        self.assertEqual(self.controller.history.events[-1].label, "Protected input")
        self.assertEqual(self.controller.history.events[-1].count, 1)

    def test_bottom_right_position_tracks_parent(self):
        self.controller.settings.corner = "bottom_right"
        self.controller.settings.margin = 20
        self.controller.overlay.refresh_geometry()
        position = self.controller.overlay.pos()
        self.assertEqual(position.x(), self.target.width() - self.controller.overlay.width() - 20)
        self.assertEqual(position.y(), self.target.height() - self.controller.overlay.height() - 20)

    def test_keyboard_text_can_be_placed_on_either_side_of_mouse(self):
        overlay = self.controller.overlay
        overlay.settings.show_mouse_icon = True
        overlay.settings.mouse_size = 54

        overlay.settings.keyboard_side = "right"
        right_text_x, right_mouse_x = overlay._content_x_positions(80, True)
        self.assertEqual(right_mouse_x, 16)
        self.assertGreater(right_text_x, right_mouse_x)

        overlay.settings.keyboard_side = "left"
        left_text_x, left_mouse_x = overlay._content_x_positions(80, True)
        self.assertEqual(left_text_x, 16)
        self.assertGreater(left_mouse_x, left_text_x)

    def test_scroll_direction_is_shown_temporarily_on_mouse(self):
        self.controller.overlay.show_scroll("up", duration=0.6)
        self.assertEqual(self.controller.overlay.scroll_direction, "up")
        expires = self.controller.overlay.scroll_expires
        self.assertTrue(self.controller.overlay.expire_scroll(expires + 0.01))
        self.assertIsNone(self.controller.overlay.scroll_direction)

if __name__ == "__main__":
    unittest.main()
