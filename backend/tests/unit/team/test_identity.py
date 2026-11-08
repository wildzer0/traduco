import time

from app.core.team import policy, session
from app.core.team.identity import User, roles_from_claims


def test_roles_come_from_the_claim_whatever_the_provider_prefixes() -> None:
    claims = {
        "roles": ["traduco-author", "offline_access", "Reviewer"],
        "realm_access": {"roles": ["traduco/admin"]},
    }
    assert roles_from_claims(claims, "roles") == ("author", "reviewer")
    assert roles_from_claims(claims, "realm_access.roles") == ("admin",)
    assert roles_from_claims({"roles": "admin"}, "roles") == ("admin",)
    assert roles_from_claims({"roles": ["staff"]}, "roles") == ()
    assert roles_from_claims({"roles": ["staff"]}, "roles", default="reviewer") == ("reviewer",)
    assert roles_from_claims({}, "missing.path") == ()


def test_what_each_role_may_do() -> None:
    reviewer, author, admin = (User("s", "n", roles=(r,)) for r in ("reviewer", "author", "admin"))
    assert (
        reviewer.can("approve")
        and not reviewer.can("edit_source")
        and not reviewer.can("configure")
    )
    assert author.can("edit_source") and author.can("configure") and not author.can("approve")
    assert all(admin.can(p) for p in ("approve", "edit_source", "admin"))
    both = User("s", "n", roles=("author", "reviewer"))
    assert both.can("approve") and both.can("edit_source") and not both.can("admin")
    assert not User("s", "n").can("read")  # no role, no permission


def test_a_session_cookie_cannot_be_forged_or_kept_past_its_time() -> None:
    secret = "k" * 40
    user = User("sub-1", "Anna", "a@x.it", ("author",))
    token = session.session_token(user, secret, hours=1)
    assert session.user_from_token(token, secret) == user
    assert session.user_from_token(token, "other-secret" * 4) is None
    raw, _, mac = token.partition(".")
    assert session.user_from_token(raw + "x." + mac, secret) is None
    assert (
        session.user_from_token(None, secret) is None
        and session.user_from_token("junk", secret) is None
    )
    expired = session.sign({"sub": "x"}, secret, ttl_seconds=-5)
    assert session.verify(expired, secret) is None
    assert session.verify(session.sign({"a": 1}, secret, 60), "") is None
    time.sleep(0)


def test_get_routes_are_readable_and_unlisted_writes_need_the_administrator() -> None:
    assert policy.required("GET", "/api/projects/{project_id}/tree") == "read"
    assert policy.required("GET", "/api/settings") == "admin"
    assert policy.required("PUT", "/api/projects/{project_id}/files") == "edit_source"
    assert policy.required("POST", "/api/something/new") == "admin"
