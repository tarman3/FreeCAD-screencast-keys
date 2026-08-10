"""Transparent painted overlay containing key history and mouse state."""

from .qt import QtCore, QtGui, QtWidgets, qt_value


class ScreencastOverlay(QtWidgets.QWidget):
    def __init__(self, parent, history, settings):
        super().__init__(parent)
        self.history = history
        self.settings = settings
        self.pressed_buttons = set()
        self.scroll_direction = None
        self.scroll_expires = 0.0
        self.setObjectName("ScreencastKeysOverlay")
        self.setAttribute(qt_value("WA_TransparentForMouseEvents", "WidgetAttribute"), True)
        self.setAttribute(qt_value("WA_TranslucentBackground", "WidgetAttribute"), True)
        self.setFocusPolicy(qt_value("NoFocus", "FocusPolicy"))
        self.hide()

    def apply_settings(self, settings):
        self.settings = settings
        self.history.configure(settings.max_history, settings.display_time)
        self.refresh_geometry()
        self.update()

    def set_button(self, button, pressed):
        if pressed:
            self.pressed_buttons.add(button)
        else:
            self.pressed_buttons.discard(button)
        self.update()

    def show_scroll(self, direction, duration=0.6):
        self.scroll_direction = direction
        self.scroll_expires = self.history.now() + duration
        self.update()

    def expire_scroll(self, now=None):
        now = self.history.now() if now is None else now
        if self.scroll_direction is not None and now >= self.scroll_expires:
            self.scroll_direction = None
            self.update()
            return True
        return False

    def clear_input_state(self):
        self.pressed_buttons.clear()
        self.scroll_direction = None
        self.scroll_expires = 0.0
        self.update()

    def refresh_geometry(self):
        hint = self.sizeHint()
        self.resize(hint)
        self.reposition()

    def _display_font(self):
        font = QtGui.QFont(self.font())
        font.setPointSize(self.settings.font_size)
        font.setWeight(QtGui.QFont.DemiBold)
        return font

    def sizeHint(self):
        metrics = QtGui.QFontMetrics(self._display_font())
        labels = [event.display_text(self.settings.repeat_count) for event in self.history.events]
        widest = max([metrics.horizontalAdvance(label) for label in labels] + [0])
        line_height = metrics.height() + 5
        text_height = line_height * len(labels)
        mouse_width = self.settings.mouse_size if self.settings.show_mouse_icon else 0
        gap = 16 if mouse_width and labels else 0
        mouse_height = int(self.settings.mouse_size * 1.35) if self.settings.show_mouse_icon else 0
        height = max(text_height, mouse_height, line_height) + 28
        width = widest + mouse_width + gap + 32
        return QtCore.QSize(width, height)

    def reposition(self):
        parent = self.parentWidget()
        if parent is None:
            return
        margin = self.settings.margin
        x = margin if self.settings.corner.endswith("left") else parent.width() - self.width() - margin
        y = margin if self.settings.corner.startswith("top") else parent.height() - self.height() - margin
        self.move(max(0, x), max(0, y))
        self.raise_()

    def _content_x_positions(self, text_width, has_labels):
        padding = 16
        mouse_x = padding
        text_x = padding
        if self.settings.show_mouse_icon:
            gap = 16 if has_labels else 0
            if self.settings.keyboard_side == "left":
                mouse_x += text_width + gap
            else:
                text_x += self.settings.mouse_size + gap
        return text_x, mouse_x

    def paintEvent(self, _event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)

        background = QtGui.QColor(self.settings.background_color)
        background.setAlphaF(self.settings.background_opacity / 100.0)
        painter.setPen(qt_value("NoPen", "PenStyle"))
        painter.setBrush(background)
        painter.drawRoundedRect(self.rect(), 12, 12)

        font = self._display_font()
        painter.setFont(font)
        metrics = QtGui.QFontMetrics(font)
        events = self.history.events
        widest = max(
            [
                metrics.horizontalAdvance(event.display_text(self.settings.repeat_count))
                for event in events
            ]
            + [0]
        )
        text_x, mouse_x = self._content_x_positions(widest, bool(events))
        if self.settings.show_mouse_icon:
            self._draw_mouse(
                painter,
                mouse_x,
                (self.height() - int(self.settings.mouse_size * 1.35)) // 2,
            )

        line_height = metrics.height() + 5
        content_height = max(1, len(events)) * line_height
        y = (self.height() - content_height) // 2 + metrics.ascent()
        now = self.history.now()
        for event in events:
            color = QtGui.QColor(self.settings.text_color)
            color.setAlphaF(self.history.opacity(event, now))
            painter.setPen(color)
            painter.drawText(text_x, y, event.display_text(self.settings.repeat_count))
            y += line_height

    def _draw_mouse(self, painter, x, y):
        width = self.settings.mouse_size
        height = int(width * 1.35)
        button_height = int(height * 0.38)
        outline = QtGui.QColor(self.settings.text_color)
        accent = QtGui.QColor(self.settings.accent_color)
        pen = QtGui.QPen(outline, max(2.0, width / 24.0))
        pen.setJoinStyle(qt_value("RoundJoin", "PenJoinStyle"))
        painter.setPen(pen)
        painter.setBrush(qt_value("NoBrush", "BrushStyle"))
        body = QtCore.QRectF(x, y, width, height)
        painter.drawRoundedRect(body, width * 0.42, width * 0.42)

        third = width / 3.0
        button_rects = {
            "left": QtCore.QRectF(x + 2, y + 2, third - 3, button_height - 2),
            "middle": QtCore.QRectF(x + third + 1, y + 2, third - 2, button_height - 2),
            "right": QtCore.QRectF(x + 2 * third + 1, y + 2, third - 3, button_height - 2),
        }
        painter.save()
        clip = QtGui.QPainterPath()
        clip.addRoundedRect(body.adjusted(2, 2, -2, -2), width * 0.38, width * 0.38)
        painter.setClipPath(clip)
        painter.setPen(qt_value("NoPen", "PenStyle"))
        painter.setBrush(accent)
        for name in self.pressed_buttons:
            rect = button_rects.get(name)
            if rect is not None:
                painter.drawRect(rect)
        if self.scroll_direction is not None:
            rect = button_rects["middle"]
            gradient = self._scroll_gradient(rect, accent)
            painter.setBrush(gradient)
            painter.drawRect(rect)
        painter.restore()

        painter.setPen(pen)
        painter.drawLine(QtCore.QPointF(x, y + button_height), QtCore.QPointF(x + width, y + button_height))
        painter.drawLine(QtCore.QPointF(x + third, y), QtCore.QPointF(x + third, y + button_height))
        painter.drawLine(QtCore.QPointF(x + 2 * third, y), QtCore.QPointF(x + 2 * third, y + button_height))

    def _scroll_gradient(self, rect, accent):
        if self.scroll_direction == "up":
            start, end = rect.topLeft(), rect.bottomLeft()
        elif self.scroll_direction == "down":
            start, end = rect.bottomLeft(), rect.topLeft()
        elif self.scroll_direction == "left":
            start, end = rect.topLeft(), rect.topRight()
        else:
            start, end = rect.topRight(), rect.topLeft()
        gradient = QtGui.QLinearGradient(start, end)
        strong = QtGui.QColor(accent)
        strong.setAlpha(245)
        faint = QtGui.QColor(accent)
        faint.setAlpha(20)
        gradient.setColorAt(0.0, strong)
        gradient.setColorAt(1.0, faint)
        return gradient
