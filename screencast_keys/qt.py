"""Small Qt compatibility layer for FreeCAD's PySide wrapper and PySide6."""

try:  # FreeCAD supplies a version-independent ``PySide`` package.
    from PySide import QtCore, QtGui, QtWidgets
except ImportError:  # Allows development and tests outside FreeCAD.
    try:
        from PySide6 import QtCore, QtGui, QtWidgets
    except ImportError:
        from PySide2 import QtCore, QtGui, QtWidgets


def enum(container, name, scoped_name=None):
    """Return an enum member with support for Qt 5 and Qt 6 naming."""
    value = getattr(container, name, None)
    if value is not None:
        return value
    scope = getattr(container, scoped_name)
    return getattr(scope, name)


def enum_int(value):
    """Convert a PySide enum to int on both Qt 5 and Qt 6."""
    try:
        return int(value)
    except TypeError:
        return int(value.value)


def event_type(name):
    return enum(QtCore.QEvent, name, "Type")


def qt_value(name, scope):
    return enum(QtCore.Qt, name, scope)
