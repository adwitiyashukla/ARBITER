from arbiter.oracle.dom import find_overlaps, state_delta, disabled_inventory


def el(ref, tag="div", text="", path="body>main>div", fixed=False, rect=(0, 0, 100, 50), **kw):
    x, y, w, h = rect
    base = {"ref": ref, "tag": tag, "text": text, "value": "", "id": kw.pop("id", ""),
            "testid": kw.pop("testid", ""), "path": path, "fixed": fixed,
            "rect": {"x": x, "y": y, "w": w, "h": h}, "disabled": kw.pop("disabled", False)}
    base.update(kw)
    return base


def test_state_delta_reports_added_removed_and_text_changes():
    before = [el(0, text="one", testid="a"), el(1, text="two", testid="b")]
    after = [el(0, text="ONE", testid="a"), el(2, text="three", testid="c")]
    d = state_delta(before, after)
    assert any("c" in s for s in d["added"])
    assert any("b" in s for s in d["removed"])
    assert any("one" in s and "ONE" in s for s in d["text_changed"])


def test_state_delta_reports_enable_changes():
    before = [el(0, testid="fmt", disabled=True)]
    after = [el(0, testid="fmt", disabled=False)]
    assert state_delta(before, after)["enabled_changed"]


def test_overlap_detects_pinned_bar_covering_content():
    bar = el(0, tag="div", text="Dashboard", path="body>div#fixedbar", fixed=True,
             rect=(0, 0, 520, 76), id="fixedbar")
    card = el(1, tag="div", text="Revenue", path="body>main>div#firstCard",
              rect=(16, 52, 488, 90), id="firstCard")
    found = find_overlaps([bar, card])
    assert found, "a fixed bar covering a card must be reported"
    assert found[0][2] > 0.15


def test_overlap_ignores_ancestors():
    outer = el(0, tag="header", text="Site", path="body>header", fixed=True, rect=(0, 0, 600, 60))
    inner = el(1, tag="span", text="Logo", path="body>header>span", rect=(10, 10, 80, 30))
    assert find_overlaps([outer, inner]) == [], "a bar must not be reported as covering its own child"


def test_overlap_reports_a_bar_that_completely_swallows_a_heading():
    """The regression the smoke test caught: total covering was being treated as
    containment and skipped, which threw away the strongest possible evidence."""
    bar = el(0, tag="div", text="Dashboard", path="body>div#topbar", fixed=True,
             rect=(0, 0, 520, 85), id="topbar")
    heading = el(1, tag="strong", text="Revenue", path="body>main>div#firstCard>strong",
                 rect=(32, 68, 70, 21))
    found = find_overlaps([bar, heading])
    assert found and found[0][2] > 0.5


def test_overlap_ignores_a_fullscreen_backdrop():
    """A modal overlay covering the page is doing its job, not exhibiting a bug."""
    overlay = el(0, tag="div", text="", path="body>div#overlay", fixed=True,
                 rect=(0, 0, 900, 700), id="overlay")
    behind = el(1, tag="button", text="Open settings", path="body>main>button",
                rect=(20, 100, 140, 36))
    assert find_overlaps([overlay, behind], viewport={"width": 900, "height": 700}) == []
    # without a viewport there is nothing to compare against, so it is still reported
    assert find_overlaps([overlay, behind]) != []


def test_overlap_ignores_content_that_wraps_the_pinned_element():
    bar = el(0, tag="div", text="Bar", path="body>div#bar", fixed=True, rect=(100, 100, 80, 20))
    wrapper = el(1, tag="section", text="Section", path="body>section", rect=(0, 0, 400, 300))
    assert find_overlaps([bar, wrapper]) == []


def test_disabled_inventory_lists_disabled_controls():
    els = [el(0, testid="fmt", disabled=True), el(1, testid="ok")]
    assert disabled_inventory(els) == ["div#fmt"]
