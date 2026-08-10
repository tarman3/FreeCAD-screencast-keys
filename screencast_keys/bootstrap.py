"""Registration with the FreeCAD GUI."""

import os

from .qt import QtCore


_controller = None
ICON_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "Resources", "icons")


def get_controller():
    return _controller


def _initialize_now():
    global _controller
    if _controller is not None:
        return
    import FreeCADGui
    from .controller import ScreencastController

    main_window = FreeCADGui.getMainWindow()
    if main_window is None:
        return
    _controller = ScreencastController(main_window)
    _controller.start()


def initialize():
    """Register preferences, then create widgets after GUI startup."""
    import FreeCADGui
    from .preferences import ScreencastKeysPreferencesPage

    FreeCADGui.addIconPath(ICON_DIR)
    FreeCADGui.addPreferencePage(ScreencastKeysPreferencesPage, "Screencast Keys")
    QtCore.QTimer.singleShot(0, _initialize_now)
