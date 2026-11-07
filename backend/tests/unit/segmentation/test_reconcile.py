from app.core.segmentation.reconcile import Match, reconcile
from app.core.segmentation.segmenter import segment


def old_of(text: str) -> list[tuple[str, str]]:
    return [(s.key, s.hash) for s in segment(text).segments]


def test_unchanged_segments_match_exactly() -> None:
    text = "# T\n\nuno\n\ndue\n"
    new = segment(text).segments
    got = reconcile(old_of(text), new)
    assert all(m and m.exact for m in got.values())


def test_edit_pairs_by_position_and_is_not_exact() -> None:
    new = segment("# T\n\nuno\n\ndue modificato\n").segments
    got = reconcile(old_of("# T\n\nuno\n\ndue\n"), new)
    assert got["p:0"] == Match("p:0", True)
    assert got["p:1"] == Match("p:1", False)


def test_moved_paragraph_keeps_its_translation() -> None:
    got = reconcile(old_of("uno\n\ndue\n\ntre\n"), segment("tre\n\nuno\n\ndue\n").segments)
    assert got["p:0"] == Match("p:2", True)
    assert got["p:1"] == Match("p:0", True)


def test_inserted_paragraph_has_no_predecessor() -> None:
    got = reconcile(old_of("uno\n\ndue\n"), segment("uno\n\nnuovo\n\ndue\n").segments)
    assert got["p:0"] == Match("p:0", True)
    assert got["p:2"] == Match("p:1", True)
    assert got["p:1"] is None


def test_different_kinds_never_pair() -> None:
    got = reconcile(old_of("# Titolo\n"), segment("testo diverso\n").segments)
    assert got["p:0"] is None
