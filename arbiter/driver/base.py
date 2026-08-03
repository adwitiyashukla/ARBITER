"""Driver interface.

Everything above this line in the stack (perception format, action vocabulary, oracles,
judge) is platform independent. Swapping this interface for an adb or Appium
implementation is the documented path to running ARBITER against a mobile app.
"""
from __future__ import annotations

from typing import Any, Dict, List, Sequence, Tuple

from ..models import Action


class Driver:
    name = "base"

    def start(self) -> None:
        raise NotImplementedError

    def stop(self) -> None:
        raise NotImplementedError

    def goto(self, url: str) -> None:
        raise NotImplementedError

    def snapshot(self) -> Tuple[List[Dict[str, Any]], bytes]:
        """Return the element map and a raw screenshot."""
        raise NotImplementedError

    def act(self, action: Action) -> str:
        """Execute one action, returning a short human-readable result string."""
        raise NotImplementedError

    def act_with_burst(self, action: Action, frames: int, interval_ms: int
                       ) -> Tuple[str, List[Any], List[float]]:
        """Execute an action while capturing a burst of frames for the visual oracle."""
        raise NotImplementedError

    @property
    def url(self) -> str:
        raise NotImplementedError
