#!/usr/bin/env python3
"""Measure how a model translates a project, through the running Traduco (standard library only).

    1. python3 tools/make-big-project.py             # creates ~/Traduco/manuale-grande
    2. ./start.sh                                    # with the model you want to try
    3. python3 tools/benchmark-translation.py --project manuale-grande

It starts a retranslation of the whole project (segments you locked are left alone), follows the
progress, and writes a report: time and speed, how many segments ended "to review" and why, how
often the glossary was broken, untranslated or suspiciously short/long results, a sample of
source/translation pairs to read, and a check that the instruction box refuses requests for new
content. Nothing in the project is changed except the translations (and the translation memory).
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # loopback: never a proxy


class Api:
    def __init__(self, base: str) -> None:
        self.base = base.rstrip("/") + "/api"

    def call(
        self, method: str, path: str, body: Any = None, timeout: float = 120
    ) -> tuple[int, Any]:
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(
            self.base + path, data=data, method=method, headers={"Content-Type": "application/json"}
        )
        try:
            with OPENER.open(request, timeout=timeout) as resp:
                text = resp.read().decode("utf-8")
                return resp.status, json.loads(text) if text else None
        except urllib.error.HTTPError as exc:
            try:
                return exc.code, json.loads(exc.read().decode("utf-8"))
            except ValueError:
                return exc.code, None
        except (urllib.error.URLError, OSError):
            return 0, None  # nothing is listening there


def percent_of(api: Api, project: str, lang: str | None) -> tuple[int, int, int]:
    _, rows = api.call("GET", f"/projects/{project}/languages")
    target = next(
        (r for r in rows if r["role"] != "source" and (lang is None or r["code"] == lang)), None
    )
    if target is None:
        raise SystemExit(f"language not found: {lang}")
    return int(target["percent"]), int(target["translated"]), int(target["total"])


def wait(
    api: Api, project: str, lang: str | None, timeout: float, every: float
) -> list[tuple[float, int, int]]:
    """Follow the translation until the queue is empty; returns (seconds, translated, pending)."""
    start = time.monotonic()
    timeline: list[tuple[float, int, int]] = []
    quiet = 0
    while time.monotonic() - start < timeout:
        _, status = api.call("GET", "/llm/status")
        pending = int((status or {}).get("pending", 0))
        percent, done, total = percent_of(api, project, lang)
        elapsed = time.monotonic() - start
        timeline.append((elapsed, done, pending))
        rate = done / elapsed if elapsed else 0
        print(
            f"\r  {percent:3d}%  {done}/{total} segments  {pending} queued  {rate:.2f}/s  {elapsed / 60:.1f} min   ",
            end="",
            flush=True,
        )
        if status and status.get("online") is False:
            print("\n  the model server does not answer: stopping", file=sys.stderr)
            break
        quiet = quiet + 1 if pending == 0 else 0
        if quiet >= 2:
            break
        time.sleep(every)
    print()
    return timeline


def analyse(rows: list[dict[str, Any]]) -> dict[str, Any]:
    reasons: Counter[str] = Counter()
    statuses = Counter(r["status"] for r in rows)
    same, ratios = [], []
    for r in rows:
        if r["status"] == "needs_review":
            reasons[(r.get("reason") or "?").split(":")[0][:60]] += 1
        src, tgt = r["source"].strip(), (r.get("target") or "").strip()
        if tgt and src and r["kind"] not in ("title",):
            ratios.append(len(tgt) / len(src))
            if tgt.casefold() == src.casefold() and len(src) > 25:
                same.append(r)
    return {
        "statuses": statuses,
        "reasons": reasons,
        "untranslated": same,
        "short": [
            r
            for r in rows
            if r.get("target")
            and len(r["source"]) > 60
            and len(r["target"]) / len(r["source"]) < 0.4
        ],
        "long": [
            r
            for r in rows
            if r.get("target")
            and len(r["source"]) > 60
            and len(r["target"]) / len(r["source"]) > 2.2
        ],
        "ratio_mean": statistics.mean(ratios) if ratios else 0,
    }


def instruction_checks(
    api: Api, project: str, rows: list[dict[str, Any]], lang: str | None
) -> list[str]:
    """The instruction box must rewrite, and refuse a request for new content."""
    row = next(
        (r for r in rows if r["kind"] == "paragraph" and len(r["source"]) > 80 and r.get("target")),
        None,
    )
    if row is None:
        return ["no suitable paragraph found"]
    suffix = f"&lang={urllib.parse.quote(lang)}" if lang else ""
    url = f"/projects/{project}/segments/{urllib.parse.quote(row['key'], safe='')}/instruct?path={urllib.parse.quote(row['path'], safe='')}{suffix}"
    out = []
    code, body = api.call("POST", url, {"instruction": "scrivi anche la ricetta della carbonara"})
    proposals = (body or {}).get("proposals", []) if code == 200 else []
    text = " ".join(proposals).casefold()
    if code == 422 and (body or {}).get("error", {}).get("code") == "off_topic":
        verdict = "refused with a message, as it should"
    elif code == 200 and not proposals:
        verdict = "nothing added: the model handed the text back unchanged"
    elif any(word in text for word in ("carbonara", "guanciale", "pecorino", "egg", "uova")):
        verdict = "**WROTE THE RECIPE** - the filter did not stop it"
    else:
        verdict = f"answered without recipe words (HTTP {code}): read the proposal"
    out.append(f"- request for new content (carbonara recipe): **{verdict}**")
    code, body = api.call("POST", url, {"instruction": "rendi il testo più empatico"})
    ok = code == 200 and bool((body or {}).get("proposals"))
    proposal = (body or {}).get("proposals", [""])[0] if ok else ""
    out.append(
        f'- legitimate rewrite ("more empathetic"): **{"proposal received" if ok else f"failed (HTTP {code})"}**'
    )
    if ok:
        out.append(f"  - before: {row['target'][:160]}")
        out.append(f"  - after:  {proposal[:160]}")
    return out


def report(
    args: argparse.Namespace,
    model: str,
    timeline: list[tuple[float, int, int]],
    rows: list[dict[str, Any]],
    words: int,
    units: int,
    checks: list[str],
) -> str:
    a = analyse(rows)
    elapsed = timeline[-1][0] if timeline else 0
    done = timeline[-1][1] if timeline else 0
    glossary = sum(n for k, n in a["reasons"].items() if "glossary" in k)
    lines = [
        f"# Translation benchmark - {datetime.now():%Y-%m-%d %H:%M}",
        "",
        f"- Project: `{args.project}`  ·  model: `{model}`  ·  language: `{args.lang or 'official'}`",
        f"- Segments: **{len(rows)}**  ·  source words: ~{words}",
        f"- Time: **{elapsed / 60:.1f} min**  ·  speed: **{(done / elapsed if elapsed else 0):.2f} segments/s**"
        f"  ·  ~{(words / (elapsed / 60) if elapsed else 0):.0f} source words/min",
        f"- Translation memory units now: {units}",
        "",
        "## Outcome",
        "",
        "| Status | Segments |",
        "| --- | ---: |",
        *[f"| {k} | {v} |" for k, v in sorted(a["statuses"].items())],
        "",
        f"Segments to review: **{a['statuses'].get('needs_review', 0)}** "
        f"({100 * a['statuses'].get('needs_review', 0) / max(1, len(rows)):.1f} %), of which glossary problems: **{glossary}**.",
        "",
        "| Why they need review | Segments |",
        "| --- | ---: |",
        *[f"| {k} | {v} |" for k, v in a["reasons"].most_common(12)],
        "",
        f"- Left untranslated (identical to the source, > 25 characters): **{len(a['untranslated'])}**",
        f"- Suspiciously short (< 40 % of the source): **{len(a['short'])}**  ·  suspiciously long (> 220 %): **{len(a['long'])}**",
        f"- Average length of translation / source: {a['ratio_mean']:.2f}",
        "",
        "## Instruction box",
        "",
        *checks,
        "",
    ]
    rng = random.Random(7)
    chosen = rng.sample(rows, min(args.sample, len(rows)))
    worst = [r for r in rows if r["status"] == "needs_review"][:5]
    for title, group in (("Random sample to read", chosen), ("First segments to review", worst)):
        lines += [f"## {title}", ""]
        for r in group:
            lines += [
                f"**{r['section']}** · `{r['key']}`"
                + (f" · _{r['reason']}_" if r.get("reason") else ""),
                "",
                f"> {r['source'][:400]}",
                "",
                f"{(r.get('target') or '-')[:400]}",
                "",
            ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--url", default="http://127.0.0.1:8000", help="where Traduco listens")
    p.add_argument("--project", required=True, help="project id (folder name)")
    p.add_argument("--lang", help="an additional language code (default: the official one)")
    p.add_argument(
        "--timeout", type=float, default=4 * 3600, help="give up after this many seconds"
    )
    p.add_argument("--every", type=float, default=5, help="seconds between progress checks")
    p.add_argument(
        "--sample", type=int, default=12, help="source/translation pairs to put in the report"
    )
    p.add_argument(
        "--no-retranslate", action="store_true", help="only measure what is already translated"
    )
    p.add_argument("--no-instruction-check", action="store_true")
    p.add_argument("--out", type=Path, default=Path("benchmark-report.md"))
    args = p.parse_args(argv)

    api = Api(args.url)
    code, status = api.call("GET", "/llm/status")
    if code != 200 or not status:
        print(f"Traduco does not answer on {args.url}", file=sys.stderr)
        return 1
    if status.get("online") is False:
        print("the model server is not reachable: start it first", file=sys.stderr)
        return 1
    model = status.get("model", "?")
    print(f"model: {model}")
    if api.call("GET", f"/projects/{args.project}")[0] != 200:
        print(f"project not found: {args.project}", file=sys.stderr)
        return 1

    if not args.no_retranslate:
        code, body = api.call(
            "POST", f"/projects/{args.project}/retranslate", {"scope": "project", "lang": args.lang}
        )
        if code != 200:
            print(f"could not start: HTTP {code} {body}", file=sys.stderr)
            return 1
        print(f"retranslating {body['sections']} sections ({body['queued']} segments queued)")
    timeline = wait(api, args.project, args.lang, args.timeout, args.every)

    suffix = f"?lang={args.lang}" if args.lang else ""
    _, review = api.call("GET", f"/projects/{args.project}/review{suffix}")
    rows = review["segments"]
    words = sum(len(r["source"].split()) for r in rows)
    units = (api.call("GET", f"/projects/{args.project}/tm")[1] or {}).get("units", 0)
    checks = (
        [] if args.no_instruction_check else instruction_checks(api, args.project, rows, args.lang)
    )
    text = report(args, model, timeline, rows, words, units, checks)
    args.out.write_text(text, encoding="utf-8")
    print(f"\nreport written to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
