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


def test_overlap_ignores_ancestor_and_containment():
    outer = el(0, tag="header", text="Site", path="body>header", fixed=True, rect=(0, 0, 600, 60))
    inner = el(1, tag="span", text="Logo", path="body>header>span", rect=(10, 10, 80, 30))
    assert find_overlaps([outer, inner]) == []


def test_disabled_inventory_lists_disabled_controls():
    els = [el(0, testid="fmt", disabled=True), el(1, testid="ok")]
    assert disabled_inventory(els) == ["div#fmt"]
