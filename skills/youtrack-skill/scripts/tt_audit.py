#!/usr/bin/env python3
"""Audit YouTrack projects: which have Time Tracking enabled and actually working.

Usage:
    python3 tt_audit.py [--days N] [--json] [--threshold N]

Categories (default thresholds: --days=90, --threshold=20):
    🟢 enabled + work items recorded
    🔴 enabled but 0 work items while active (>= threshold issues updated)
    🟠 disabled but active (>= threshold issues updated)
    ⚪ no activity — skipped from problem buckets
"""
from __future__ import annotations

import os
import sys
import json
import argparse
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from yt_client import YouTrackClient, load_env  # noqa: E402


def api(client: YouTrackClient, path: str, params: dict | None = None):
    url = client.base_url + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {client.api_key}",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def audit(days: int) -> list[dict]:
    load_env()
    c = YouTrackClient()
    since_iso = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")

    projects = api(c, "/api/admin/projects", {
        "fields": "id,shortName,name,archived",
        "$top": "500",
    })
    active = [p for p in projects if not p.get("archived")]

    rows = []
    for p in active:
        pid, sn, name = p["id"], p["shortName"], p["name"]
        try:
            tt = api(c, f"/api/admin/projects/{pid}/timeTrackingSettings",
                     {"fields": "enabled"})
            tt_enabled = bool(tt.get("enabled"))
        except Exception:
            tt_enabled = None

        try:
            issues = api(c, "/api/issues", {
                "query": f"project: {{{name}}} updated: {since_iso} .. Today",
                "fields": "id",
                "$top": "1000",
            })
            issues_n = len(issues)
        except Exception:
            issues_n = -1

        try:
            wi = api(c, "/api/workItems", {
                "fields": "id,duration(minutes)",
                "query": f"project: {{{name}}} work date: {since_iso} .. Today",
                "$top": "1000",
            })
            wi_n = len(wi)
            wi_min = sum((w.get("duration") or {}).get("minutes", 0) for w in wi)
        except Exception:
            wi_n, wi_min = -1, 0

        rows.append({
            "shortName": sn, "name": name,
            "tt_enabled": tt_enabled,
            "issues": issues_n, "work_items": wi_n, "work_minutes": wi_min,
        })
        print(f"  {sn:14s} tt={tt_enabled} issues={issues_n} wi={wi_n} min={wi_min}",
              file=sys.stderr)
    return rows


def categorize(rows: list[dict], threshold: int) -> dict:
    ok, broken, missing, idle = [], [], [], []
    for r in rows:
        active = r["issues"] >= threshold
        if r["tt_enabled"] and r["work_items"] > 0:
            ok.append(r)
        elif r["tt_enabled"] and active and r["work_items"] == 0:
            broken.append(r)
        elif not r["tt_enabled"] and active:
            missing.append(r)
        else:
            idle.append(r)
    return {"ok": ok, "broken": broken, "missing": missing, "idle": idle}


def render_table(title: str, rows: list[dict], days: int):
    if not rows:
        print(f"\n## {title}\n  (none)")
        return
    print(f"\n## {title}")
    print(f"{'Project':16s} {'Issues':>7s} {'WorkItems':>10s} {'Hours':>8s}  Name")
    for r in sorted(rows, key=lambda x: -x["issues"]):
        hours = r["work_minutes"] // 60
        print(f"{r['shortName']:16s} {r['issues']:>7d} {r['work_items']:>10d} {hours:>8d}  {r['name']}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=90, help="lookback window (default 90)")
    ap.add_argument("--threshold", type=int, default=20,
                    help="min issues updated in window to call project 'active' (default 20)")
    ap.add_argument("--json", action="store_true", help="emit raw JSON instead of tables")
    args = ap.parse_args()

    rows = audit(args.days)
    cats = categorize(rows, args.threshold)

    if args.json:
        print(json.dumps({"days": args.days, "threshold": args.threshold,
                          "categories": cats}, ensure_ascii=False, indent=2))
        return

    print(f"\n# YouTrack Time Tracking audit — last {args.days} days "
          f"(active = >= {args.threshold} updated issues)")
    render_table("🟢 Enabled + working", cats["ok"], args.days)
    render_table("🔴 Enabled but NOT collecting (active project, 0 work items)",
                 cats["broken"], args.days)
    render_table("🟠 NOT enabled (but active development)", cats["missing"], args.days)
    print(f"\n⚪ Idle / inactive: {len(cats['idle'])} projects (skipped)")


if __name__ == "__main__":
    main()
