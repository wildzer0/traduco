"""Section locks and presence."""

import pytest

from app.core.team.coordination import MemoryCoordination
from app.core.team.identity import User
from app.core.workspace.errors import WorkspaceError

ANNA = User("a", "Anna", roles=("author",))
BRUNO = User("b", "Bruno", roles=("author",))
S = "capitoli/01-a/01-x.md"


class Clock:
    now = 0.0

    def __call__(self) -> float:
        return self.now


def make() -> tuple[MemoryCoordination, Clock]:
    clock = Clock()
    return MemoryCoordination(ttl=10, clock=clock), clock


def test_the_first_to_edit_gets_the_lock_and_the_other_only_looks() -> None:
    c, _ = make()
    assert c.heartbeat("p", ANNA, S, edit=True).editing
    seat = c.heartbeat("p", BRUNO, S, edit=True)
    assert not seat.editing
    assert c.holder("p", S) == "Anna"


def test_a_write_by_someone_else_is_refused_and_by_the_holder_allowed() -> None:
    c, _ = make()
    c.heartbeat("p", ANNA, S, edit=True)
    with pytest.raises(WorkspaceError) as err:
        c.check_write("p", BRUNO, S)
    assert err.value.code == "locked"
    c.check_write("p", ANNA, S)


def test_a_write_takes_the_lock_when_nobody_has_it() -> None:
    c, _ = make()
    c.check_write("p", ANNA, S)
    assert c.holder("p", S) == "Anna"


def test_the_lock_expires_without_heartbeats() -> None:
    c, clock = make()
    c.heartbeat("p", ANNA, S, edit=True)
    clock.now = 11
    assert c.holder("p", S) is None
    c.check_write("p", BRUNO, S)
    assert c.holder("p", S) == "Bruno"


def test_moving_to_another_section_frees_the_previous_one() -> None:
    c, _ = make()
    c.heartbeat("p", ANNA, S, edit=True)
    c.heartbeat("p", ANNA, "capitoli/01-a/02-y.md", edit=True)
    assert c.holder("p", S) is None


def test_projects_do_not_share_locks_and_leaving_releases() -> None:
    c, _ = make()
    c.heartbeat("p", ANNA, S, edit=True)
    c.check_write("q", BRUNO, S)
    c.release("p", ANNA)
    assert c.seats("p") == []
