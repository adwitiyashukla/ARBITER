"""Structural oracle over the element map produced by perception.

Reports what changed in the DOM and what geometry looks wrong. It deliberately does
not know anything about any particular bug: it emits deltas and overlaps, and lets
the judge decide whether they match the report.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

OVERLAP_MIN_RATIO = 0.15     # fraction of an element that must be covered to count
MAX_DELTA_ITEMS = 12         # keep prompts bounded


def element_key(el: Dict[str, Any]) -> str:
    """A reasonably stable identity for an element across snapshots."""
    for field in ("testid", "id"):
        if el.get(field):
            return "{0}#{1}".format(el.get("tag", "?"), el[field])
    label = (el.get("text") or el.get("value") or "")[:40]
    return "{0}:{1}".format(el.get("tag", "?"), label)


def _area(rect: Dict[str, float]) -> float:
    return max(0.0, float(rect.get("w", 0))) * max(0.0, float(rect.get("h", 0)))


def _intersection(a: Dict[str, float], b: Dict[str, float]) -> float:
    ax2, ay2 = a["x"] + a["w"], a["y"] + a["h"]
    bx2, by2 = b["x"] + b["w"], b["y"] + b["h"]
    w = min(ax2, bx2) - max(a["x"], b["x"])
    h = min(ay2, by2) - max(a["y"], b["y"])
    return max(0.0, w) * max(0.0, h)


def _contains(outer: Dict[str, float], inner: Dict[str, float]) -> bool:
    return (outer["x"] <= inner["x"] and outer["y"] <= inner["y"]
            and outer["x"] + outer["w"] >= inner["x"] + inner["w"]
            and outer["y"] + outer["h"] >= inner["y"] + inner["h"])


def state_delta(before: List[Dict[str, Any]], after: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    """Human-readable diff of two element maps."""
    b = {element_key(e): e for e in before}
    a = {element_key(e): e for e in after}
    delta: Dict[str, List[str]] = {"added": [], "removed": [], "text_changed": [],
                                   "enabled_changed": [], "value_changed": []}
    for k in a:
        if k not in b:
            label = (a[k].get("text") or a[k].get("value") or a[k].get("tag", ""))[:60]
            delta["added"].append("{0} {1!r}".format(k, label))
    for k in b:
        if k not in a:
            label = (b[k].get("text") or b[k].get("value") or b[k].get("tag", ""))[:60]
            delta["removed"].append("{0} {1!r}".format(k, label))
    for k in set(a) & set(b):
        if (b[k].get("text") or "") != (a[k].get("text") or ""):
            delta["text_changed"].append("{0}: {1!r} -> {2!r}".format(
                k, (b[k].get("text") or "")[:40], (a[k].get("text") or "")[:40]))
        if (b[k].get("value") or "") != (a[k].get("value") or ""):
            delta["value_changed"].append("{0}: {1!r} -> {2!r}".format(
                k, (b[k].get("value") or "")[:40], (a[k].get("value") or "")[:40]))
        if bool(b[k].get("disabled")) != bool(a[k].get("disabled")):
            delta["enabled_changed"].append("{0}: disabled {1} -> {2}".format(
                k, bool(b[k].get("disabled")), bool(a[k].get("disabled"))))
    for key in delta:
        delta[key] = delta[key][:MAX_DELTA_ITEMS]
    return delta


def find_overlaps(elements: List[Dict[str, Any]]) -> List[Tuple[str, str, float]]:
    """Pinned elements that visually cover unrelated content."""
    out = []
    pinned = [e for e in elements if e.get("fixed") and _area(e.get("rect", {})) > 0]
    others = [e for e in elements if not e.get("fixed") and (e.get("text") or "").strip()
              and _area(e.get("rect", {})) > 0]
    for f in pinned:
        fp = f.get("path", "")
        for e in others:
            ep = e.get("path", "")
            if fp and ep and (ep.startswith(fp) or fp.startswith(ep)):
                continue                                    # ancestor or descendant
            if _contains(f["rect"], e["rect"]) or _contains(e["rect"], f["rect"]):
                continue                                    # containment, not a collision
            inter = _intersection(f["rect"], e["rect"])
            if inter <= 0:
                continue
            ratio = inter / _area(e["rect"])
            if ratio >= OVERLAP_MIN_RATIO:
                out.append((element_key(f), element_key(e), ratio))
    return sorted(out, key=lambda t: -t[2])[:5]


def disabled_inventory(elements: List[Dict[str, Any]]) -> List[str]:
    return [element_key(e) for e in elements if e.get("disabled")][:MAX_DELTA_ITEMS]


class DomOracle:
    source = "dom"

    def inspect(self, step: int, before: Optional[List[Dict[str, Any]]],
                after: List[Dict[str, Any]]) -> List["object"]:
        from ..models import Signal
        signals: List[Signal] = []

        if before is not None:
            delta = state_delta(before, after)
            summary = {k: v for k, v in delta.items() if v}
            if summary:
                parts = ["{0}: {1}".format(k, "; ".join(v)) for k, v in summary.items()]
                signals.append(Signal(self.source, "state_delta", " | ".join(parts)[:600],
                                      step, "info", {"delta": delta}))
            else:
                signals.append(Signal(self.source, "no_dom_change",
                                      "the element map is identical before and after this action",
                                      step, "notable", {}))

        overlaps = find_overlaps(after)
        for f_key, e_key, ratio in overlaps:
            signals.append(Signal(
                self.source, "overlap",
                "pinned element {0} covers {1:.0%} of {2}".format(f_key, ratio, e_key),
                step, "hard", {"covering": f_key, "covered": e_key, "ratio": round(ratio, 3)}))

        disabled = disabled_inventory(after)
        if disabled:
            signals.append(Signal(self.source, "disabled_elements",
                                  "currently disabled: " + ", ".join(disabled),
                                  step, "info", {"disabled": disabled}))
        return signals
