"""Verified, resumable downloads and safe archive extraction (RF-77, ADR-014).

Standard library only: ``urllib`` honours ``HTTP_PROXY``/``HTTPS_PROXY`` automatically.
"""

from __future__ import annotations

import hashlib
import http.client
import shutil
import tarfile
import time
import urllib.error
import urllib.request
import zipfile
from collections.abc import Callable
from pathlib import Path

from launcher.ui import LauncherError

Progress = Callable[[int, int | None], None]
CHUNK = 64 * 1024
USER_AGENT = "traduco-launcher/0.1"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _total_size(resp: http.client.HTTPResponse, offset: int) -> int | None:
    if resp.status == 206:
        rng = resp.headers.get("Content-Range", "")  # "bytes 100-999/1000"
        if "/" in rng and rng.rsplit("/", 1)[1].isdigit():
            return int(rng.rsplit("/", 1)[1])
    length = resp.headers.get("Content-Length")
    if length and length.isdigit():
        return int(length) + (offset if resp.status == 206 else 0)
    return None


def _fetch_into(url: str, part: Path, timeout: float, progress: Progress | None) -> None:
    offset = part.stat().st_size if part.exists() else 0
    headers = {"User-Agent": USER_AGENT}
    if offset:
        headers["Range"] = f"bytes={offset}-"
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=timeout) as r:
        resumed = r.status == 206
        if offset and not resumed:  # server ignored Range: start over
            offset = 0
        total = _total_size(r, offset if resumed else 0)
        done = offset
        with part.open("ab" if resumed else "wb") as out:
            while block := r.read(CHUNK):
                out.write(block)
                done += len(block)
                if progress:
                    progress(done, total)
    if total is not None and done < total:  # http.client does not flag a truncated body
        raise ConnectionError(f"connection closed early ({done}/{total} bytes)")


def download(
    url: str,
    dest: Path,
    sha256: str,
    *,
    offline: bool = False,
    retries: int = 3,
    timeout: float = 30,
    backoff: float = 2.0,
    progress: Progress | None = None,
) -> Path:
    """Download ``url`` to ``dest`` and verify its SHA-256. Always verified, even when cached."""
    sha256 = sha256.lower()
    if dest.is_file():
        if sha256_file(dest) == sha256:
            return dest
        dest.unlink()
    if offline:
        raise LauncherError("E012", name=dest.name)
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    reason = "unknown"
    for attempt in range(1, retries + 1):
        resumed = part.exists() and part.stat().st_size > 0
        try:
            _fetch_into(url, part, timeout, progress)
        except urllib.error.HTTPError as exc:
            if exc.code == 416 and resumed:  # nothing left to fetch, or a stale partial file
                pass
            elif 400 <= exc.code < 500:
                raise LauncherError("E010", url=url, reason=f"HTTP {exc.code}") from exc
            else:
                reason = f"HTTP {exc.code}"
                time.sleep(backoff * attempt)
                continue
        except (urllib.error.URLError, OSError, http.client.HTTPException, TimeoutError) as exc:
            reason = str(getattr(exc, "reason", exc))
            time.sleep(backoff * attempt)
            continue
        if sha256_file(part) == sha256:
            part.replace(dest)
            return dest
        part.unlink(missing_ok=True)
        if not resumed:
            raise LauncherError("E011", name=dest.name)
        reason = "checksum mismatch after resume"  # retry once from scratch
    raise LauncherError("E010", url=url, reason=reason)


def _safe_target(base: Path, name: str) -> Path:
    target = (base / name).resolve()
    if base.resolve() not in (target, *target.parents):
        raise LauncherError("E020", what=f"unsafe path in archive: {name}")
    return target


def extract_archive(archive: Path, dest: Path) -> None:
    """Extract a .zip, .tar.gz or .tar.xz into ``dest``, rejecting paths that escape it."""
    dest.mkdir(parents=True, exist_ok=True)
    if archive.suffix == ".zip":
        with zipfile.ZipFile(archive) as zf:
            for member in zf.infolist():
                _safe_target(dest, member.filename)
            zf.extractall(dest)
            for member in zf.infolist():  # zipfile drops the executable bit
                mode = member.external_attr >> 16
                if mode & 0o111:
                    (dest / member.filename).chmod(mode & 0o777)
    else:
        with tarfile.open(archive) as tf:
            tf.extractall(dest, filter="data")


def install_archive(archive: Path, target: Path) -> None:
    """Extract ``archive`` and move its single top-level folder (if any) to ``target``."""
    tmp = target.with_name(target.name + ".tmp")
    shutil.rmtree(tmp, ignore_errors=True)
    extract_archive(archive, tmp)
    entries = list(tmp.iterdir())
    source = entries[0] if len(entries) == 1 and entries[0].is_dir() else tmp
    shutil.rmtree(target, ignore_errors=True)
    shutil.move(str(source), str(target))
    shutil.rmtree(tmp, ignore_errors=True)
