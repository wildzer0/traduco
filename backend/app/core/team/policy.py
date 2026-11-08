"""Which permission each route needs in team mode.

Every route that changes something is listed by hand. A route that is not listed needs ``admin``,
and a test checks that none is missing, so adding an endpoint without deciding who may call it is
caught when the tests run, not by a user.
"""

from __future__ import annotations

P = "/api/projects/{project_id}"

#: (method, path template) -> permission. GET routes default to ``read``, see GET_EXCEPTIONS.
ROUTES: dict[tuple[str, str], str] = {
    # project, settings
    ("POST", "/api/projects"): "admin",
    ("PATCH", P): "configure",
    ("PUT", "/api/settings"): "admin",
    ("POST", "/api/auth/logout"): "read",  # also open without a session, see guard.PUBLIC
    # the text
    ("PUT", f"{P}/files"): "edit_source",
    ("POST", f"{P}/nodes"): "edit_source",
    ("PATCH", f"{P}/nodes"): "edit_source",
    ("DELETE", f"{P}/nodes"): "edit_source",
    ("PATCH", f"{P}/sections/meta"): "edit_source",
    ("POST", f"{P}/assets"): "edit_source",
    ("PUT", f"{P}/diagrams/{{digest}}"): "read",  # a cache of the preview, not a document change
    ("POST", f"{P}/assist"): "read",  # only proposes
    ("POST", f"{P}/assist/apply"): "edit_source",
    ("POST", f"{P}/snippets/{{alias}}/expand"): "edit_source",  # inserts text and moves a counter
    ("POST", f"{P}/spellcheck"): "read",
    # translations (approving is decided inside the endpoint: it needs ``approve``)
    ("PUT", f"{P}/segments/{{key}}"): "edit_translation",
    ("POST", f"{P}/segments/{{key}}/instruct"): "edit_translation",
    ("POST", f"{P}/segments/{{key}}/back-translate"): "edit_translation",
    ("POST", f"{P}/segments/{{key}}/apply-source"): "edit_source",
    ("POST", f"{P}/retranslate"): "edit_translation",
    # review
    ("POST", f"{P}/comments"): "comment",
    ("POST", f"{P}/comments/{{thread_id}}/reply"): "comment",
    ("PATCH", f"{P}/comments/{{thread_id}}"): "comment",
    ("DELETE", f"{P}/comments/{{thread_id}}"): "comment",
    ("POST", f"{P}/check"): "comment",
    ("POST", f"{P}/check/dismiss"): "comment",
    # documents
    ("POST", f"{P}/export"): "export",
    ("POST", f"{P}/import"): "edit_source",
    ("POST", f"{P}/import/{{job_id}}/proposals/{{proposal_id}}"): "edit_source",
    # project configuration
    ("PUT", f"{P}/glossary"): "configure",
    ("POST", f"{P}/glossary/import"): "configure",
    ("POST", f"{P}/tm/import"): "configure",
    ("PUT", f"{P}/skeleton"): "configure",
    ("POST", f"{P}/skeleton/create-missing"): "configure",
    ("PUT", f"{P}/snippets"): "configure",
    ("POST", f"{P}/templates"): "configure",
    ("POST", f"{P}/templates/example"): "configure",
    ("POST", f"{P}/templates/wizard"): "configure",
    ("PUT", f"{P}/templates/{{name}}"): "configure",
    ("DELETE", f"{P}/templates/{{name}}"): "configure",
    ("PUT", f"{P}/templates/{{name}}/default"): "configure",
    ("POST", f"{P}/issues"): "configure",
    ("DELETE", f"{P}/issues/{{rev}}"): "configure",
    ("POST", f"{P}/issues/{{rev}}/changes"): "configure",
    ("PUT", f"{P}/issues/{{rev}}/changes"): "configure",
    ("POST", f"{P}/issues/{{rev}}/changes/use"): "configure",
    ("POST", f"{P}/issues/{{rev}}/restore"): "edit_source",  # puts an old text back
}

GET_EXCEPTIONS: dict[str, str] = {
    "/api/settings": "admin",
    "/api/audit": "admin",
}


def required(method: str, template: str) -> str:
    """The permission needed for ``method`` on the route ``template``."""
    method = method.upper()
    if method in ("GET", "HEAD", "OPTIONS", "WS"):
        return GET_EXCEPTIONS.get(template, "read")
    return ROUTES.get((method, template), "admin")
