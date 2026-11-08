"""OpenID Connect login (authorization code + PKCE) against the organisation's own provider.

Only the provider named in ``TRADUCO_OIDC_ISSUER`` is ever contacted (Keycloak in the compose
profile ``team``, or any other). The ID token is checked completely: signature against the
provider's keys, issuer, audience, expiry and the nonce of this very login.
"""

from __future__ import annotations

import base64
import hashlib
import secrets
import time
from typing import Any
from urllib.parse import urlencode

import httpx
import jwt

from app.config import Settings

from .identity import User, roles_from_claims

ALGORITHMS = ["RS256", "RS384", "RS512", "ES256", "ES384", "PS256"]
KEYS_TTL = 600.0


class OidcError(Exception):
    """The login cannot be completed; the message is safe to show to the user."""


def _challenge(verifier: str) -> str:
    return (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    )


class OidcClient:
    def __init__(
        self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None
    ) -> None:
        if not settings.oidc_issuer:
            raise OidcError("TRADUCO_OIDC_ISSUER is not set")
        self.settings = settings
        self._http = httpx.AsyncClient(timeout=10.0, transport=transport)
        self._meta: dict[str, Any] | None = None
        self._keys: dict[str, jwt.PyJWK] = {}
        self._keys_at = 0.0

    async def aclose(self) -> None:
        await self._http.aclose()

    async def metadata(self) -> dict[str, Any]:
        if self._meta is None:
            url = self.settings.oidc_issuer.rstrip("/") + "/.well-known/openid-configuration"
            try:
                response = await self._http.get(url)
                response.raise_for_status()
                meta = response.json()
            except (httpx.HTTPError, ValueError) as exc:
                raise OidcError(
                    f"the identity provider does not answer: {type(exc).__name__} {exc}".strip()
                ) from exc
            for key in ("authorization_endpoint", "token_endpoint", "jwks_uri", "issuer"):
                if key not in meta:
                    raise OidcError(f"the identity provider's configuration lacks {key}")
            self._meta = meta
        return self._meta

    async def start(self, redirect_uri: str, next_url: str) -> tuple[str, dict[str, str]]:
        """The address to send the browser to, and what to remember until it comes back."""
        meta = await self.metadata()
        state, nonce = secrets.token_urlsafe(24), secrets.token_urlsafe(24)
        verifier = secrets.token_urlsafe(48)
        query = urlencode(
            {
                "response_type": "code", "client_id": self.settings.oidc_client_id,
                "redirect_uri": redirect_uri, "scope": self.settings.oidc_scopes,
                "state": state, "nonce": nonce,
                "code_challenge": _challenge(verifier), "code_challenge_method": "S256",
            }
        )  # fmt: skip
        separator = "&" if "?" in meta["authorization_endpoint"] else "?"
        remembered = {"state": state, "nonce": nonce, "verifier": verifier, "next": next_url}
        return f"{meta['authorization_endpoint']}{separator}{query}", remembered

    async def _signing_key(self, token: str) -> jwt.PyJWK:
        try:
            kid = jwt.get_unverified_header(token).get("kid", "")
        except jwt.PyJWTError as exc:
            raise OidcError("the token is not valid") from exc
        if kid not in self._keys or time.monotonic() - self._keys_at > KEYS_TTL:
            meta = await self.metadata()
            try:
                response = await self._http.get(meta["jwks_uri"])
                response.raise_for_status()
                keys = response.json().get("keys", [])
            except (httpx.HTTPError, ValueError) as exc:
                raise OidcError(f"the provider's keys cannot be read: {exc}") from exc
            self._keys = {
                k.get("kid", ""): jwt.PyJWK.from_dict(k)
                for k in keys
                if k.get("use", "sig") == "sig"
            }
            self._keys_at = time.monotonic()
        if kid not in self._keys:
            raise OidcError("the token is signed with an unknown key")
        return self._keys[kid]

    async def _decode(self, token: str, *, audience: bool) -> dict[str, Any]:
        meta = await self.metadata()
        key = await self._signing_key(token)
        try:
            claims: dict[str, Any] = jwt.decode(
                token,
                key.key,
                algorithms=ALGORITHMS,
                audience=self.settings.oidc_client_id if audience else None,
                issuer=meta["issuer"],
                options={"require": ["exp", "sub"], "verify_aud": audience},
                leeway=30,
            )
        except jwt.PyJWTError as exc:
            raise OidcError(f"the token was refused: {exc}") from exc
        return claims

    async def finish(
        self, code: str, state: str, remembered: dict[str, str], redirect_uri: str
    ) -> User:
        """Exchange the code for tokens and turn the ID token into a :class:`User`."""
        if not remembered or not secrets.compare_digest(state, remembered.get("state", "")):
            raise OidcError("this login did not start here (state does not match)")
        meta = await self.metadata()
        data = {
            "grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri,
            "client_id": self.settings.oidc_client_id, "code_verifier": remembered["verifier"],
        }  # fmt: skip
        if self.settings.oidc_client_secret:
            data["client_secret"] = self.settings.oidc_client_secret
        try:
            response = await self._http.post(meta["token_endpoint"], data=data)
        except httpx.HTTPError as exc:
            raise OidcError(
                f"the identity provider does not answer: {type(exc).__name__} {exc}".strip()
            ) from exc
        if response.status_code != 200:
            raise OidcError("the identity provider refused the login")
        tokens = response.json()
        id_token = tokens.get("id_token")
        if not id_token:
            raise OidcError("the provider sent no ID token")
        claims = await self._decode(id_token, audience=True)
        if not secrets.compare_digest(str(claims.get("nonce", "")), remembered["nonce"]):
            raise OidcError("the ID token belongs to another login (nonce does not match)")
        roles = roles_from_claims(
            claims, self.settings.oidc_roles_claim, self.settings.oidc_default_role
        )
        if not roles and tokens.get("access_token"):
            # Keycloak keeps roles in the access token unless told to repeat them in the ID token
            try:
                access = await self._decode(tokens["access_token"], audience=False)
            except OidcError:
                access = {}
            roles = roles_from_claims(
                access, self.settings.oidc_roles_claim, self.settings.oidc_default_role
            )
        if not roles:
            raise OidcError("you have no role in Traduco: ask an administrator to give you one")
        return User(
            sub=str(claims["sub"]),
            name=str(claims.get("name") or claims.get("preferred_username") or ""),
            email=str(claims.get("email") or ""),
            roles=roles,
        )
