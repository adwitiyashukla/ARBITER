import numpy as np

from arbiter.oracle.visual import analyze_burst

H, W = 120, 320


def _frame_with_box(x: int) -> np.ndarray:
    f = np.full((H, W), 240, dtype=np.uint8)
    f[20:100, max(0, x):max(0, x) + 80] = 20
    return f


def smooth_slide(n=12, step=20):
    return [_frame_with_box(i * step) for i in range(n)]


def stepped_slide(n=12):
    positions = [0] * 4 + [100] * 4 + [200] * 4
    return [_frame_with_box(p) for p in positions[:n]]


def static(n=12):
    return [_frame_with_box(0) for _ in range(n)]


def test_static_burst_is_a_no_op():
    a = analyze_burst(static())
    assert a.no_op is True
    assert a.stepped is False


def test_smooth_animation_is_not_flagged():
    a = analyze_burst(smooth_slide())
    assert a.no_op is False
    assert a.stepped is False, "a smooth slide must not be reported as jank"
    assert a.active_ratio > 0.8


def test_stepped_animation_is_flagged_as_jank():
    a = analyze_burst(stepped_slide())
    assert a.no_op is False
    assert a.stepped is True, "a three-jump animation must be reported as jank"
    assert a.max_freeze_run >= 1
    assert a.concentration >= 0.6


def test_single_instant_change_is_not_jank():
    frames = [_frame_with_box(0)] * 6 + [_frame_with_box(200)] * 6
    a = analyze_burst(frames)
    assert a.instant is True
    assert a.stepped is False, "an un-animated instant change is not an animation bug"


def test_capture_stall_is_detected_from_timestamps():
    frames = smooth_slide()
    stamps = [i * 70.0 for i in range(len(frames))]
    stamps[5] += 600
    for i in range(6, len(stamps)):
        stamps[i] += 600
    a = analyze_burst(frames, stamps)
    assert a.stalled is True


def test_oracle_emits_signals():
    from arbiter.oracle import VisualOracle
    sigs = VisualOracle().inspect(3, stepped_slide())
    kinds = {s.kind for s in sigs}
    assert "stepped_animation" in kinds
    assert all(s.step == 3 for s in sigs)
