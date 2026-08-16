"""Toolkit-independent event history model."""

from dataclasses import dataclass
import time


@dataclass
class DisplayEvent:
    label: str
    created: float
    expires: float
    duration: float
    count: int = 1

    def display_text(self, show_repeat=True):
        if show_repeat and self.count > 1:
            return "{} ×{}".format(self.label, self.count)
        return self.label


class EventHistory:
    """Bounded, expiring, consecutive-event history."""

    def __init__(self, maximum=5, duration=2.5, clock=None):
        self.maximum = maximum
        self.duration = duration
        self._clock = clock or time.monotonic
        self.events = []

    def configure(self, maximum, duration):
        self.maximum = max(1, int(maximum))
        self.duration = max(0.01, float(duration))
        self.events = self.events[-self.maximum :]

    def add(self, label, combine=True, duration=None):
        now = self._clock()
        self.expire(now)
        event_duration = self.duration if duration is None else max(0.01, float(duration))
        if combine and self.events and self.events[-1].label == label:
            event = self.events[-1]
            event.count += 1
            event.created = now
            event.expires = now + event_duration
            event.duration = event_duration
        else:
            event = DisplayEvent(label, now, now + event_duration, event_duration)
            self.events.append(event)
            self.events = self.events[-self.maximum :]
        return event

    def expire(self, now=None):
        now = self._clock() if now is None else now
        old_length = len(self.events)
        self.events = [event for event in self.events if event.expires > now]
        return len(self.events) != old_length

    def clear(self):
        self.events.clear()

    def now(self):
        return self._clock()

    def opacity(self, event, now=None):
        """Fade only during the final quarter of an event's lifetime."""
        now = self.now() if now is None else now
        remaining = event.expires - now
        fade_window = max(0.1, event.duration * 0.25)
        return max(0.0, min(1.0, remaining / fade_window))
