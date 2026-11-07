import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "check_licenses", Path(__file__).resolve().parents[1] / "check-licenses.py"
)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_simple_allowed_and_denied() -> None:
    assert mod.expression_ok("MIT")
    assert not mod.expression_ok("GPL-3.0-only")
    assert not mod.expression_ok("LGPL-2.1-or-later")
    assert not mod.expression_ok("UNKNOWN")


def test_or_needs_one_and_needs_all() -> None:
    assert mod.expression_ok("GPL-3.0-only OR MIT")
    assert mod.expression_ok("(MIT OR Apache-2.0)")
    assert not mod.expression_ok("MIT AND GPL-3.0-only")
    assert mod.expression_ok("MIT AND BSD-3-Clause")


def test_ofl_only_for_fontsource() -> None:
    assert mod.expression_ok("OFL-1.1", "@fontsource/inter")
    assert not mod.expression_ok("OFL-1.1", "some-library")
