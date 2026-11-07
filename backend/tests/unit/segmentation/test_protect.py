import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.core.segmentation.protect import PlaceholderError, check, protect, restore


def test_protects_code_urls_fields_and_terms() -> None:
    src = "Usa `make test` su https://example.com/a?b=1, vedi {{codice}} e ACME Pump."
    p = protect(src, ["ACME Pump"])
    assert "make test" not in p.text
    assert "example.com" not in p.text
    assert "{{codice}}" not in p.text
    assert "ACME Pump" not in p.text
    assert p.text.startswith("Usa ⟦1⟧ su ⟦2⟧, vedi ⟦3⟧ e ⟦4⟧.")
    assert restore(p.text, p) == src


def test_links_images_and_emphasis_keep_translatable_text() -> None:
    src = 'Vedi [la guida](docs/a.md "t"), ![schema](img/s.png) e **molto _importante_**.'
    p = protect(src)
    assert "la guida" in p.text and "schema" in p.text and "molto" in p.text
    assert "docs/a.md" not in p.text and "img/s.png" not in p.text
    assert "**" not in p.text and "_" not in p.text
    assert restore(p.text, p) == src


def test_translated_text_around_placeholders() -> None:
    p = protect("Premi **Invio** per `salvare`.")
    out = restore("Press ⟦2⟧Enter⟦/2⟧ to ⟦1⟧.", p)
    assert out == "Press **Enter** to `salvare`."


@pytest.mark.parametrize(
    "bad",
    [
        "Press Enter to ⟦1⟧.",  # pair lost
        "Press ⟦2⟧Enter to ⟦1⟧.",  # not closed
        "Press ⟦2⟧Enter⟦/2⟧ to.",  # atom lost
        "Press ⟦2⟧Enter⟦/2⟧ ⟦1⟧ ⟦1⟧.",  # atom duplicated
        "Press ⟦2⟧Enter⟦/2⟧ ⟦1⟧ ⟦9⟧.",  # invented
        "Press ⟦/2⟧Enter⟦2⟧ ⟦1⟧.",  # reversed
    ],
)
def test_broken_placeholders_are_rejected(bad: str) -> None:
    p = protect("Premi **Invio** per `salvare`.")
    with pytest.raises(PlaceholderError):
        restore(bad, p)


def test_literal_marker_characters_are_protected() -> None:
    p = protect("a ⟦1⟧ b")
    assert restore(p.text, p) == "a ⟦1⟧ b"


def test_snake_case_and_list_stars_are_not_emphasis() -> None:
    p = protect("il file my_var_name e 2 * 3 * 4")
    assert restore(p.text, p) == "il file my_var_name e 2 * 3 * 4"
    assert not p.pairs


def test_escapes_are_atoms() -> None:
    p = protect(r"prezzo 5\* e a \| b")
    assert "\\" not in p.text
    assert restore(p.text, p) == r"prezzo 5\* e a \| b"


@given(st.text(alphabet=st.sampled_from(list('ab _*`[]()!{}|\\<>/.:~#\n"⟦⟧12 ')), max_size=60))
def test_identity_roundtrip_for_any_text(src: str) -> None:
    p = protect(src, ["ab"])
    assert restore(p.text, p) == src


def test_emphasis_that_would_cross_another_pair_is_left_as_text() -> None:
    """Found by the property test: ``_:*_*`` used to give ``⟦2⟧:⟦1⟧⟦/2⟧⟦/1⟧``."""
    p = protect("_:*_*")
    assert restore(p.text, p) == "_:*_*"
    check(p.text, p)
