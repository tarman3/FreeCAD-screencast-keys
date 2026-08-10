"""Application-wide event capture and overlay lifecycle."""

import sys
import time

from .model import EventHistory
from .overlay import ScreencastOverlay
from .qt import QtCore, QtGui, QtWidgets, enum_int, event_type, qt_value
from . import settings as settings_store


_KEY_NAMES = {
    "Key_Return": "Enter",
    "Key_Enter": "Enter",
    "Key_Escape": "Esc",
    "Key_Tab": "Tab",
    "Key_Backtab": "Shift + Tab",
    "Key_Backspace": "Backspace",
    "Key_Space": "Space",
    "Key_Delete": "Delete",
    "Key_Insert": "Insert",
    "Key_Home": "Home",
    "Key_End": "End",
    "Key_PageUp": "Page Up",
    "Key_PageDown": "Page Down",
    "Key_Left": "Left",
    "Key_Right": "Right",
    "Key_Up": "Up",
    "Key_Down": "Down",
    "Key_Control": "Ctrl",
    "Key_Shift": "Shift",
    "Key_Alt": "Alt",
    "Key_Meta": "Meta",
    "Key_CapsLock": "Caps Lock",
    "Key_NumLock": "Num Lock",
    "Key_ScrollLock": "Scroll Lock",
    "Key_Pause": "Pause",
    "Key_Print": "Print Screen",
    "Key_Menu": "Menu",
    "Key_AltGr": "AltGr",
}


def _key_constant(name):
    value = getattr(QtCore.Qt, name, None)
    if value is not None:
        return value
    return getattr(QtCore.Qt.Key, name, None)


SPECIAL_KEYS = {
    enum_int(value): label
    for name, label in _KEY_NAMES.items()
    for value in [_key_constant(name)]
    if value is not None
}

MODIFIER_KEYS = {
    key: label
    for key, label in SPECIAL_KEYS.items()
    if label in {"Ctrl", "Shift", "Alt", "Meta", "AltGr"}
}


def _has_modifier(modifiers, name):
    flag = qt_value(name, "KeyboardModifier")
    return bool(enum_int(modifiers) & enum_int(flag))


def key_event_text(event, held_modifier_keys=()):
    """Create a compact, platform-neutral label from a QKeyEvent."""
    key = enum_int(event.key())
    base = SPECIAL_KEYS.get(key)
    if base is None:
        base = QtGui.QKeySequence(key).toString(QtGui.QKeySequence.NativeText)
    if not base:
        text = event.text()
        base = text.upper() if text and text.isprintable() else "Unknown"

    if key in MODIFIER_KEYS:
        return base

    held_labels = {
        MODIFIER_KEYS[enum_int(held_key)]
        for held_key in held_modifier_keys
        if enum_int(held_key) in MODIFIER_KEYS
    }
    parts = []
    for flag, label in (
        ("ControlModifier", "Ctrl"),
        ("AltModifier", "Alt"),
        ("ShiftModifier", "Shift"),
        ("MetaModifier", "Cmd" if sys.platform == "darwin" else "Meta"),
    ):
        held_label = "Meta" if label == "Cmd" else label
        if _has_modifier(event.modifiers(), flag) or held_label in held_labels:
            parts.append(label)
    if base == "Shift + Tab" and "Shift" in parts:
        parts.remove("Shift")
    parts.append(base)
    return " + ".join(parts)


def shortcut_event_text(event):
    """Return display parts and a label for a completed Qt shortcut."""
    sequence = event.key()
    portable_text = getattr(QtGui.QKeySequence, "PortableText", None)
    if portable_text is None:
        portable_text = QtGui.QKeySequence.SequenceFormat.PortableText
    raw = sequence.toString(portable_text)
    parts = [
        " + ".join(token.strip() for token in chord.split("+") if token.strip())
        for chord in raw.split(",")
        if chord.strip()
    ]
    return parts, " + ".join(parts)


def modifier_keys_text(keys):
    """Return held modifier names in the same order as shortcut labels."""
    labels = {MODIFIER_KEYS[key] for key in keys if key in MODIFIER_KEYS}
    ordered = []
    for label in ("Ctrl", "Alt", "Shift", "Meta", "AltGr"):
        if label in labels:
            ordered.append("Cmd" if label == "Meta" and sys.platform == "darwin" else label)
    return " + ".join(ordered)


def mouse_button_name(button):
    value = enum_int(button)
    mapping = {
        enum_int(qt_value("LeftButton", "MouseButton")): "left",
        enum_int(qt_value("MiddleButton", "MouseButton")): "middle",
        enum_int(qt_value("RightButton", "MouseButton")): "right",
    }
    return mapping.get(value)


class ScreencastController(QtCore.QObject):
    def __init__(self, main_window, application=None):
        super().__init__(main_window)
        self.main_window = main_window
        self.application = application or QtWidgets.QApplication.instance()
        self.settings = settings_store.load()
        self.history = EventHistory(self.settings.max_history, self.settings.display_time)
        self.target = main_window.centralWidget() or main_window
        self.overlay = ScreencastOverlay(self.target, self.history, self.settings)
        self.enabled = False
        self._last_input_signature = None
        self._last_input_seen = 0.0
        self._last_mouse_press_seen = {}
        self._last_key_press_seen = {}
        self._pressed_keys = set()
        self._held_modifier_event = None
        self._held_modifier_is_chord = False

        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(50)
        self._timer.timeout.connect(self._tick)
        self.application.installEventFilter(self)

    def start(self):
        if self.settings.enable_on_startup:
            self.set_enabled(True)

    def shutdown(self):
        self.set_enabled(False)
        self.application.removeEventFilter(self)
        self.overlay.deleteLater()

    def set_enabled(self, enabled):
        enabled = bool(enabled)
        if self.enabled == enabled:
            return
        self.enabled = enabled
        if enabled:
            self._ensure_target()
            self.overlay.refresh_geometry()
            self.overlay.show()
            self.overlay.raise_()
            self._timer.start()
        else:
            self._timer.stop()
            self.history.clear()
            self.overlay.clear_input_state()
            self._last_mouse_press_seen.clear()
            self._last_key_press_seen.clear()
            self._pressed_keys.clear()
            self._held_modifier_event = None
            self._held_modifier_is_chord = False
            self.overlay.hide()

    def toggle(self):
        self.set_enabled(not self.enabled)

    def reload_settings(self):
        self.settings = settings_store.load()
        self.overlay.apply_settings(self.settings)

    def _ensure_target(self):
        target = self.main_window.centralWidget() or self.main_window
        if target is not self.target:
            self.target = target
            self.overlay.setParent(target)
            if self.enabled:
                self.overlay.show()
        self.overlay.reposition()

    def _tick(self):
        changed = self.history.expire()
        self.overlay.expire_scroll()
        self._ensure_target()
        if changed:
            self.overlay.refresh_geometry()
        else:
            self.overlay.update()

    def _add_history(self, label, combine=True):
        if not label:
            return None
        event = self.history.add(label, combine=combine)
        self.overlay.refresh_geometry()
        self.overlay.raise_()
        return event

    def _add_protected_history(self):
        # Keep a single generic notification; do not expose password length
        # through a repeat counter or one history row per character.
        now = self.history.now()
        self.history.expire(now)
        if self.history.events and self.history.events[-1].label == "Protected input":
            event = self.history.events[-1]
            event.created = now
            event.expires = now + self.history.duration
        else:
            self.history.add("Protected input", combine=False)
        self.overlay.refresh_geometry()
        self.overlay.raise_()

    def _finish_held_modifier_event(self):
        event = self._held_modifier_event
        if event is None:
            return
        now = self.history.now()
        event.created = now
        event.expires = now + self.history.duration
        self._held_modifier_event = None
        self._held_modifier_is_chord = False
        self.overlay.refresh_geometry()

    def _show_held_modifier_event(self, label, is_chord):
        """Show a modifier label without allowing it to expire while held."""
        if not label:
            return
        event = self._held_modifier_event
        if event is not None and (not self._held_modifier_is_chord or is_chord):
            if self._held_modifier_is_chord and is_chord:
                self._finish_held_modifier_event()
                event = None
            else:
                event.label = label
                event.count = 1
        elif event is not None:
            self._finish_held_modifier_event()
            event = None
        if event is None:
            event = self._add_history(label, combine=False)
        now = self.history.now()
        event.created = now
        event.expires = float("inf")
        self._held_modifier_event = event
        self._held_modifier_is_chord = is_chord
        self.overlay.refresh_geometry()
        self.overlay.raise_()

    def _add_shortcut_history(self, event):
        """Record a completed shortcut, including multi-step sequences."""
        parts, label = shortcut_event_text(event)
        if not label:
            return
        focus = self.application.focusWidget()
        if focus is not None and self._is_password_widget(focus):
            self._add_protected_history()
            return

        now = self.history.now()
        self.history.expire(now)
        if self.history.events:
            last = self.history.events[-1]
            # ShortcutOverride may already have recorded a one-step shortcut.
            if last.label == label and now - last.created < 0.15:
                last.created = now
                if last is self._held_modifier_event:
                    last.expires = float("inf")
                else:
                    last.expires = now + self.history.duration
                self.overlay.refresh_geometry()
                self.overlay.raise_()
                return

        # Prefix keys may be delivered normally before Qt consumes the final
        # key in a multi-step shortcut. Replace that tail with one clear chord.
        maximum = min(len(parts), len(self.history.events))
        for count in range(maximum, 0, -1):
            tail = self.history.events[-count:]
            tail_labels = [item.label for item in tail]
            recent = now - tail[0].created < 1.5
            if recent and tail_labels in (parts[:count], parts[-count:]):
                del self.history.events[-count:]
                break
        self._add_history(label)

    def _is_propagated_duplicate(
        self,
        event,
        *details,
        include_timestamp=True,
        duplicate_window=0.04,
    ):
        """Recognize one native input event delivered through several widgets.

        QApplication event filters can see the same mouse/key event again as
        Qt propagates it from a child to its parents. Native copies retain the
        same timestamp. The short time guard also handles timestamp-less
        synthetic events without swallowing normal repeated input.
        """
        timestamp_method = getattr(event, "timestamp", None)
        timestamp = timestamp_method() if timestamp_method is not None else 0
        signature = (enum_int(event.type()),)
        if include_timestamp:
            signature += (int(timestamp),)
        signature += details
        now = time.monotonic()
        duplicate = (
            signature == self._last_input_signature
            and now - self._last_input_seen < duplicate_window
        )
        self._last_input_signature = signature
        self._last_input_seen = now
        return duplicate

    def _is_duplicate_mouse_press(self, event):
        """Debounce duplicate press sequences synthesized by the 3D view."""
        signature = (enum_int(event.type()), enum_int(event.button()))
        now = time.monotonic()
        previous = self._last_mouse_press_seen.get(signature, 0.0)
        self._last_mouse_press_seen[signature] = now
        return now - previous < 0.12

    def _is_duplicate_key_press(self, event):
        """Suppress propagated/synthesized copies of one physical key-down."""
        key = enum_int(event.key())
        signature = (key, enum_int(event.modifiers()), event.text())
        now = time.monotonic()
        previous = self._last_key_press_seen.get(signature, 0.0)
        self._last_key_press_seen[signature] = now

        auto_repeat = bool(event.isAutoRepeat())
        already_down = key in self._pressed_keys and not auto_repeat
        self._pressed_keys.add(key)
        debounce = 0.012 if auto_repeat else 0.08
        return already_down or now - previous < debounce

    @staticmethod
    def _is_password_widget(watched):
        widget = watched
        while widget is not None:
            if isinstance(widget, QtWidgets.QLineEdit):
                mode = widget.echoMode()
                normal = getattr(QtWidgets.QLineEdit, "Normal", None)
                if normal is None:
                    normal = QtWidgets.QLineEdit.EchoMode.Normal
                return mode != normal
            widget = widget.parentWidget() if hasattr(widget, "parentWidget") else None
        return False

    def eventFilter(self, watched, event):
        if not self.enabled:
            return False
        kind = event.type()
        if kind in (event_type("KeyPress"), event_type("ShortcutOverride")):
            if self._is_duplicate_key_press(event):
                return False
            signature = (
                enum_int(event.key()),
                enum_int(event.modifiers()),
                event.text(),
            )
            if self._is_propagated_duplicate(event, *signature):
                return False
            key = enum_int(event.key())
            if key in MODIFIER_KEYS:
                if self._is_password_widget(watched):
                    self._add_protected_history()
                    return False
                held_modifiers = self._pressed_keys.intersection(MODIFIER_KEYS)
                self._show_held_modifier_event(
                    modifier_keys_text(held_modifiers),
                    is_chord=False,
                )
                return False
            held_modifiers = self._pressed_keys.intersection(MODIFIER_KEYS)
            if self._is_password_widget(watched):
                self._add_protected_history()
            elif held_modifiers:
                self._show_held_modifier_event(
                    key_event_text(event, held_modifiers),
                    is_chord=True,
                )
            else:
                self._add_history(key_event_text(event, held_modifiers))
        elif kind == event_type("KeyRelease"):
            key = enum_int(event.key())
            self._pressed_keys.discard(key)
            if key in MODIFIER_KEYS and not event.isAutoRepeat():
                remaining = self._pressed_keys.intersection(MODIFIER_KEYS)
                self._finish_held_modifier_event()
                if remaining:
                    self._show_held_modifier_event(
                        modifier_keys_text(remaining),
                        is_chord=False,
                    )
        elif kind == event_type("Shortcut"):
            self._add_shortcut_history(event)
        elif kind in (event_type("MouseButtonPress"), event_type("MouseButtonDblClick")):
            # FreeCAD's 3D viewer can synthesize a second press with a new
            # timestamp for the same physical transition. A short timestamp-
            # independent debounce catches it. MouseButtonDblClick has a
            # different event type, so a genuine second click is retained.
            if self._is_duplicate_mouse_press(event):
                return False
            button = mouse_button_name(event.button())
            if button:
                self.overlay.set_button(button, True)
        elif kind == event_type("MouseButtonRelease"):
            if self._is_propagated_duplicate(event, enum_int(event.button())):
                return False
            button = mouse_button_name(event.button())
            if button:
                self.overlay.set_button(button, False)
        elif kind == event_type("Wheel"):
            delta = event.angleDelta()
            if self._is_propagated_duplicate(event, delta.x(), delta.y()):
                return False
            if abs(delta.y()) >= abs(delta.x()):
                direction = "up" if delta.y() >= 0 else "down"
            else:
                direction = "right" if delta.x() >= 0 else "left"
            self.overlay.show_scroll(direction)
        elif kind == event_type("ApplicationDeactivate"):
            self.overlay.clear_input_state()
            self._finish_held_modifier_event()
            self._pressed_keys.clear()
        elif watched is self.target and kind in (event_type("Resize"), event_type("Show")):
            self.overlay.reposition()
        return False
