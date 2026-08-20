"""Persistent FreeCAD preferences for Screencast Keys."""

from dataclasses import dataclass


PARAM_PATH = "User parameter:BaseApp/Preferences/Mod/ScreencastKeys"


@dataclass
class OverlaySettings:
    corner: str = "bottom_right"
    keyboard_side: str = "left"
    margin_x: int = 24
    margin_y: int = 24
    font_size: int = 22
    mouse_size: int = 54
    display_time: float = 2.5
    mouse_display_time: float = 1.0
    max_history: int = 5
    show_mouse_icon: bool = True
    show_mouse_labels: bool = True
    repeat_count: bool = True
    enable_on_startup: bool = True
    background_color: str = "#20242b"
    background_opacity: int = 82
    text_color: str = "#f4f6f8"
    accent_color: str = "#55aaff"


_memory = {}


def _params():
    try:
        import FreeCAD
        return FreeCAD.ParamGet(PARAM_PATH)
    except ImportError:
        return None


def _get(method, key, default):
    params = _params()
    if params is None:
        return _memory.get(key, default)
    return getattr(params, method)(key, default)


def load():
    """Load preferences, clamping values that affect widget geometry."""
    valid_corners = {"top_left", "top_right", "bottom_left", "bottom_right"}
    corner = _get("GetString", "Corner", "bottom_right")
    if corner not in valid_corners:
        corner = "bottom_right"
    keyboard_side = _get("GetString", "KeyboardSide", "left")
    if keyboard_side not in {"left", "right"}:
        keyboard_side = "left"
    return OverlaySettings(
        corner=corner,
        keyboard_side=keyboard_side,
        margin_x=max(0, min(500, _get("GetInt", "MarginX", 24))),
        margin_y=max(0, min(500, _get("GetInt", "MarginY", 24))),
        font_size=max(8, min(96, _get("GetInt", "FontSize", 22))),
        mouse_size=max(24, min(200, _get("GetInt", "MouseSize", 54))),
        display_time=max(0.25, min(30.0, _get("GetFloat", "DisplayTime", 2.5))),
        mouse_display_time=max(
            0.1,
            min(30.0, _get("GetFloat", "MouseDisplayTime", 1.0)),
        ),
        max_history=max(1, min(20, _get("GetInt", "MaxHistory", 5))),
        show_mouse_icon=_get("GetBool", "ShowMouseIcon", True),
        show_mouse_labels=_get("GetBool", "ShowMouseLabels", True),
        repeat_count=_get("GetBool", "RepeatCount", True),
        enable_on_startup=_get("GetBool", "EnableOnStartup", True),
        background_color=_get("GetString", "BackgroundColor", "#20242b"),
        background_opacity=max(0, min(100, _get("GetInt", "BackgroundOpacity", 82))),
        text_color=_get("GetString", "TextColor", "#f4f6f8"),
        accent_color=_get("GetString", "AccentColor", "#55aaff"),
    )


def save(values):
    """Save an OverlaySettings instance."""
    params = _params()
    entries = {
        "Corner": ("SetString", values.corner),
        "KeyboardSide": ("SetString", values.keyboard_side),
        "MarginX": ("SetInt", values.margin_x),
        "MarginY": ("SetInt", values.margin_y),
        "FontSize": ("SetInt", values.font_size),
        "MouseSize": ("SetInt", values.mouse_size),
        "DisplayTime": ("SetFloat", values.display_time),
        "MouseDisplayTime": ("SetFloat", values.mouse_display_time),
        "MaxHistory": ("SetInt", values.max_history),
        "ShowMouseIcon": ("SetBool", values.show_mouse_icon),
        "ShowMouseLabels": ("SetBool", values.show_mouse_labels),
        "RepeatCount": ("SetBool", values.repeat_count),
        "EnableOnStartup": ("SetBool", values.enable_on_startup),
        "BackgroundColor": ("SetString", values.background_color),
        "BackgroundOpacity": ("SetInt", values.background_opacity),
        "TextColor": ("SetString", values.text_color),
        "AccentColor": ("SetString", values.accent_color),
    }
    for key, (method, value) in entries.items():
        if params is None:
            _memory[key] = value
        else:
            getattr(params, method)(key, value)
    if params is not None:
        try:
            import FreeCAD
            FreeCAD.saveParameter()
        except (AttributeError, ImportError):
            pass
