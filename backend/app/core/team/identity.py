"""Who is using Traduco in team mode, and what they may do (RNF-09, ADR-046).

Three roles that can be combined: *author* writes the source and configures the project,
*reviewer* works on translations and approves them (an author cannot approve their own work unless
they are also a reviewer), *admin* can do everything and manages the server.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

ROLES = ("reviewer", "author", "admin")
PERMISSIONS = (
    "read",  # see projects, translations, previews
    "comment",  # review comments, section checks
    "export",  # produce documents
    "edit_translation",  # correct, lock, regenerate translations
    "approve",  # mark a translation as approved (feeds the translation memory)
    "edit_source",  # write sections, structure, assets, accept imported changes
    "configure",  # glossary, templates, issues, languages, metadata, skeleton, snippets
    "admin",  # create projects, model settings, audit log
)
GRANTS: dict[str, frozenset[str]] = {
    "reviewer": frozenset({"read", "comment", "export", "edit_translation", "approve"}),
    "author": frozenset(
        {"read", "comment", "export", "edit_translation", "edit_source", "configure"}
    ),
    "admin": frozenset(PERMISSIONS),
}


@dataclass(frozen=True)
class User:
    sub: str  # the identity provider's stable identifier
    name: str
    email: str = ""
    roles: tuple[str, ...] = field(default_factory=tuple)

    def can(self, permission: str) -> bool:
        return any(permission in GRANTS.get(role, ()) for role in self.roles)

    @property
    def label(self) -> str:
        return self.name or self.email or self.sub

    def public(self) -> dict[str, object]:
        return {
            "sub": self.sub,
            "name": self.label,
            "email": self.email,
            "roles": list(self.roles),
            "permissions": [p for p in PERMISSIONS if self.can(p)],
        }


def roles_from_claims(
    claims: Mapping[str, object], path: str, default: str = ""
) -> tuple[str, ...]:
    """Our roles out of the ID token: ``path`` may be dotted (``realm_access.roles``).

    Values are matched to ``reviewer``/``author``/``admin`` ignoring case and any prefix before a
    ``/``, ``:`` or ``-`` separator that the provider adds (``traduco-admin``, ``traduco/author``).
    """
    value: object = claims
    for part in path.split("."):
        value = value.get(part) if isinstance(value, Mapping) else None
    raw = [value] if isinstance(value, str) else list(value) if isinstance(value, list) else []
    found: list[str] = []
    for item in raw:
        text = str(item).casefold()
        for role in ROLES:
            matches = text == role or text.endswith(
                ("-" + role, "/" + role, ":" + role, "_" + role)
            )
            if matches and role not in found:
                found.append(role)
    if not found and default in ROLES:
        found.append(default)
    return tuple(found)
