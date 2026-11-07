import json
from pathlib import Path

from app.core.translation import store
from app.core.translation.store import SegmentFile, StoredSegment


def sample() -> SegmentFile:
    return SegmentFile(
        "sha256:abc", [StoredSegment("p:0", "sha256:1", "paragraph", "Hi", status="translated")]
    )


def test_roundtrip_and_location(tmp_path: Path) -> None:
    store.save(tmp_path, "en", "capitoli/01-a/01-b.md", sample())
    path = tmp_path / ".traduco/segmenti/en/capitoli/01-a/01-b.json"
    assert path.is_file()
    assert store.load(tmp_path, "en", "capitoli/01-a/01-b.md") == sample()


def test_json_is_sorted_and_indented_for_git(tmp_path: Path) -> None:
    store.save(tmp_path, "en", "capitoli/a.md", sample())
    text = (tmp_path / ".traduco/segmenti/en/capitoli/a.json").read_text()
    assert text.endswith("}\n") and '\n  "segments"' in text
    data = json.loads(text)
    assert list(data) == sorted(data)
    assert list(data["segments"][0]) == sorted(data["segments"][0])


def test_damaged_file_reads_as_missing(tmp_path: Path) -> None:
    path = store.segment_path(tmp_path, "en", "capitoli/a.md")
    path.parent.mkdir(parents=True)
    path.write_text("{not json")
    assert store.load(tmp_path, "en", "capitoli/a.md") is None


def test_update_mutates_in_place(tmp_path: Path) -> None:
    store.save(tmp_path, "en", "capitoli/a.md", sample())

    def mutate(f: SegmentFile) -> None:
        f.segments[0].target = "Changed"

    store.update(tmp_path, "en", "capitoli/a.md", mutate)
    loaded = store.load(tmp_path, "en", "capitoli/a.md")
    assert loaded is not None and loaded.segments[0].target == "Changed"
