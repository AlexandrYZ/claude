#!/usr/bin/env python3
"""
YouTrack CLI Client — unified command-line interface for YouTrack API.

Usage:
    python3 yt_client.py info TMK-824
    python3 yt_client.py comments TMK-824
    python3 yt_client.py comment TMK-824 "Comment text"
    python3 yt_client.py search "project: TMK status: Open"
    python3 yt_client.py create TMK "Fix login bug" --assignee user --description "Details"
    python3 yt_client.py update TMK-824 --status "In Progress" --assignee user
    python3 yt_client.py stats --tag ai --from 2026-01-01

All commands support --json flag for machine-readable output.
"""
from __future__ import annotations

import os
import sys
import json
import argparse
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path
from datetime import datetime
from collections import defaultdict


# =============================================================================
# Utilities
# =============================================================================

def load_env():
    """Load environment variables from .env file.

    Priority order:
    1. ~/.env (global user environment)
    2. <skill_dir>/.env (skill-specific environment)
    3. ./.env (current project directory)
    """
    env_paths = [
        Path.home() / ".env",
        Path(__file__).parent.parent / ".env",
        Path.cwd() / ".env",
    ]

    for env_path in env_paths:
        if env_path.exists():
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        value = value.strip('"').strip("'")
                        os.environ.setdefault(key, value)
            break


def extract_field(custom_fields: list, field_name: str) -> str:
    """Extract value from customFields list by field name."""
    for field in custom_fields:
        if field.get("name") == field_name:
            value = field.get("value")
            if value is None:
                return "-"
            if isinstance(value, dict):
                return value.get("name") or value.get("fullName") or "-"
            if isinstance(value, list):
                return ", ".join(v.get("name", "") for v in value) or "-"
    return "-"


def format_timestamp(ts: int) -> str:
    """Format millisecond timestamp to human-readable date."""
    if not ts:
        return "-"
    dt = datetime.fromtimestamp(ts / 1000)
    return dt.strftime("%d.%m.%Y %H:%M")


def format_date(ts: int) -> str:
    """Format millisecond timestamp to date only."""
    if not ts:
        return "-"
    dt = datetime.fromtimestamp(ts / 1000)
    return dt.strftime("%d.%m.%Y")


def date_to_timestamp(date_str: str) -> int:
    """Convert YYYY-MM-DD date string to millisecond timestamp."""
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    return int(dt.timestamp() * 1000)


def print_json(data):
    """Print data as formatted JSON."""
    print(json.dumps(data, indent=2, ensure_ascii=False, default=str))


# =============================================================================
# YouTrackClient
# =============================================================================

PROJECTS = {
    "ADM": "0-26",
    "FER": "0-40",
    "TMK": "0-39",
    "IREG": "0-42",
    "BI": "0-14",
    "TEL": "0-0",
    "ISMLP": "0-21",
    "MLOK": "0-23",
}


class YouTrackClient:
    """Client for YouTrack REST API."""

    DEFAULT_TOP = 500

    # fieldType.valueType -> (IssueCustomField base name, value_key). Cardinality
    # (Single/Multi prefix) comes from fieldType.isMultiValue, NOT from the
    # ProjectCustomField $type — that $type is "EnumProjectCustomField" for both
    # single and multi enums on this instance, which is why guessing $type fails.
    VALUE_TYPE_MAP = {
        "enum": ("Enum", "name"),
        "version": ("Version", "name"),
        "user": ("User", "login"),
        "ownedField": ("Owned", "name"),
        "build": ("Build", "name"),
    }

    def __init__(self, base_url: str | None = None, api_key: str | None = None):
        load_env()
        # {PROJECT: {field_name: {"valueType": str, "multi": bool}}}
        self._field_type_cache: dict[str, dict[str, dict]] = {}

        self.base_url = (
            base_url
            or os.environ.get("YOUTRACK_BASE_URL")
            or os.environ.get("YOUTRACK_URL", "https://yt.pkzdrav.ru")
        )
        self.api_key = api_key or os.environ.get("YOUTRACK_API_KEY")

        if not self.api_key:
            raise ValueError("YOUTRACK_API_KEY not set. Set environment variable or .env file.")

        self.base_url = self.base_url.rstrip("/")

    # -------------------------------------------------------------------------
    # Low-level API
    # -------------------------------------------------------------------------

    def _request(self, method: str, path: str, data: dict | None = None) -> dict | list | None:
        """Make HTTP request to YouTrack API."""
        url = f"{self.base_url}{path}"
        body = json.dumps(data).encode("utf-8") if data else None

        request = urllib.request.Request(url, data=body, method=method)
        request.add_header("Authorization", f"Bearer {self.api_key}")
        request.add_header("Accept", "application/json")
        if body:
            request.add_header("Content-Type", "application/json")

        try:
            with urllib.request.urlopen(request) as response:
                if response.status == 204:
                    return None
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            error_body = ""
            try:
                error_body = e.read().decode("utf-8")
            except Exception:
                pass
            return {"error": f"HTTP {e.code}: {e.reason}", "detail": error_body}
        except urllib.error.URLError as e:
            return {"error": str(e.reason)}

    def _get(self, path: str) -> dict | list | None:
        return self._request("GET", path)

    def _post(self, path: str, data: dict) -> dict | list | None:
        return self._request("POST", path, data)

    # -------------------------------------------------------------------------
    # Issue operations
    # -------------------------------------------------------------------------

    ISSUE_FIELDS = "idReadable,summary,description,created,updated,resolved,customFields(name,value(name,login,fullName)),tags(id,name)"

    def get_issue(self, issue_id: str) -> dict:
        """Get issue details by ID."""
        fields = urllib.parse.quote(self.ISSUE_FIELDS)
        result = self._get(f"/api/issues/{issue_id}?fields={fields}")
        if isinstance(result, dict) and "error" in result:
            result["idReadable"] = issue_id
        return result

    def get_comments(self, issue_id: str) -> list:
        """Get comments for an issue."""
        fields = "id,text,author(fullName),created"
        result = self._get(f"/api/issues/{issue_id}/comments?fields={fields}")
        if isinstance(result, list):
            return result
        return []

    def add_comment(self, issue_id: str, text: str) -> dict:
        """Add a comment to an issue."""
        data = {"text": text}
        fields = "id,text,created"
        result = self._post(f"/api/issues/{issue_id}/comments?fields={fields}", data)
        if isinstance(result, dict):
            return result
        return {"error": "Unexpected response"}

    def search_issues(
        self,
        query: str,
        top: int | None = None,
        skip: int = 0,
        fields: str | None = None,
    ) -> list:
        """Search issues with YouTrack query language. Supports pagination."""
        top = top or self.DEFAULT_TOP
        fields = fields or self.ISSUE_FIELDS
        encoded_query = urllib.parse.quote(query)
        encoded_fields = urllib.parse.quote(fields)
        url = f"/api/issues?fields={encoded_fields}&query={encoded_query}&$top={top}&$skip={skip}"
        result = self._get(url)
        if isinstance(result, list):
            return result
        return []

    def search_all_issues(self, query: str, fields: str | None = None) -> list:
        """Search all issues with automatic pagination."""
        all_issues = []
        skip = 0
        top = self.DEFAULT_TOP
        while True:
            batch = self.search_issues(query, top=top, skip=skip, fields=fields)
            if not batch:
                break
            all_issues.extend(batch)
            if len(batch) < top:
                break
            skip += top
        return all_issues

    def _resolve_project_id(self, short_name: str) -> str | None:
        """Resolve project shortName to numeric id via admin API (case-insensitive)."""
        result = self._get("/api/admin/projects?fields=id,shortName&$top=500")
        if isinstance(result, list):
            for p in result:
                if p.get("shortName", "").lower() == short_name.lower():
                    return p.get("id")
        return None

    def _project_field_types(self, project_short_name: str) -> dict[str, dict]:
        """Map field name -> {valueType, multi} for a project (cached, 1 request)."""
        key = project_short_name.upper()
        if key in self._field_type_cache:
            return self._field_type_cache[key]
        project_id = PROJECTS.get(key) or self._resolve_project_id(project_short_name)
        types: dict[str, dict] = {}
        if project_id:
            result = self._get(
                f"/api/admin/projects/{project_id}/customFields"
                f"?fields=field(name,fieldType(valueType,isMultiValue))&$top=100"
            )
            if isinstance(result, list):
                for f in result:
                    fld = f.get("field") or {}
                    name = fld.get("name")
                    ft = fld.get("fieldType") or {}
                    if name:
                        types[name] = {
                            "valueType": ft.get("valueType"),
                            "multi": bool(ft.get("isMultiValue")),
                        }
        self._field_type_cache[key] = types
        return types

    def _build_custom_field(self, project_short_name: str, name: str, value: str) -> dict:
        """Build a customFields entry with the correct $type / value shape.

        Cardinality (Single/Multi) and value shape are read from the project schema
        (fieldType.valueType + isMultiValue), so callers never guess $type. State is
        always single. User fields use {"login": ...}; enum/version/etc use {"name": ...}.
        Multi-valued fields wrap the value in a list. Unknown fields fall back to
        SingleEnum (name).
        """
        meta = self._project_field_types(project_short_name).get(name) or {}
        value_type = meta.get("valueType")
        multi = meta.get("multi", False)

        if value_type == "state":
            return {"name": name, "$type": "StateIssueCustomField", "value": {"name": value}}

        base, value_key = self.VALUE_TYPE_MAP.get(value_type, ("Enum", "name"))
        issue_type = f"{'Multi' if multi else 'Single'}{base}IssueCustomField"
        single = {value_key: value}
        return {"name": name, "$type": issue_type, "value": [single] if multi else single}

    def create_issue(
        self,
        project_id: str,
        summary: str,
        description: str | None = None,
        assignee: str | None = None,
        region: str | None = None,
        issue_type: str | None = None,
        extra_fields: dict[str, str] | None = None,
    ) -> dict:
        """Create a new issue. project_id is the project short name (e.g., TMK).

        issue_type -> Type field (Task/Bug/Epic/...); extra_fields -> arbitrary
        custom fields {"Контур": "ХМАО: Рабочий контур", ...}. All field $types are
        auto-detected from the project schema (single admin request, cached).
        """
        custom_fields = []
        if issue_type:
            custom_fields.append(self._build_custom_field(project_id, "Type", issue_type))
        if assignee:
            custom_fields.append(self._build_custom_field(project_id, "Assignee", assignee))
        if region:
            custom_fields.append(self._build_custom_field(project_id, "Регион", region))
        for fname, fvalue in (extra_fields or {}).items():
            custom_fields.append(self._build_custom_field(project_id, fname, fvalue))

        # YouTrack on this instance rejects {"shortName": ...} refs — resolve to numeric id
        numeric_id = PROJECTS.get(project_id.upper()) or self._resolve_project_id(project_id)
        project_ref = {"id": numeric_id} if numeric_id else {"shortName": project_id}

        data = {
            "project": project_ref,
            "summary": summary,
            "description": description or "",
            "customFields": custom_fields,
        }

        fields = urllib.parse.quote("idReadable,summary")
        result = self._post(f"/api/issues?fields={fields}", data)
        return result or {"error": "No response from server"}

    def update_issue(
        self,
        issue_id: str,
        summary: str | None = None,
        description: str | None = None,
    ) -> dict | None:
        """Update issue fields (summary, description)."""
        data = {}
        if summary:
            data["summary"] = summary
        if description:
            data["description"] = description
        if not data:
            return {"error": "Nothing to update"}
        fields = urllib.parse.quote("idReadable,summary")
        return self._request("POST", f"/api/issues/{issue_id}?fields={fields}", data)

    def execute_command(self, issue_id: str, command: str) -> dict | None:
        """Execute a YouTrack command on an issue."""
        data = {
            "query": command,
            "issues": [{"idReadable": issue_id}],
        }
        return self._post("/api/commands", data)

    # -------------------------------------------------------------------------
    # Statistics
    # -------------------------------------------------------------------------

    def get_tag_stats(
        self,
        tag: str,
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> dict:
        """Collect statistics for issues with a given tag."""
        query = f"tag: {tag}"
        issues = self.search_all_issues(query)

        # Client-side date filtering
        if from_date:
            from_ts = date_to_timestamp(from_date)
            issues = [i for i in issues if i.get("created", 0) >= from_ts]
        if to_date:
            to_ts = date_to_timestamp(to_date) + 86399999  # End of day
            issues = [i for i in issues if i.get("created", 0) <= to_ts]

        total = len(issues)
        status_counts = defaultdict(int)
        assignee_counts = defaultdict(int)
        project_counts = defaultdict(int)
        monthly_counts = defaultdict(int)

        for issue in issues:
            cf = issue.get("customFields", [])
            status = extract_field(cf, "Статус")
            status_counts[status] += 1

            assignee = extract_field(cf, "Assignee")
            if assignee != "-":
                assignee_counts[assignee] += 1

            issue_id = issue.get("idReadable", "")
            if "-" in issue_id:
                project_counts[issue_id.split("-")[0]] += 1

            created = issue.get("created")
            if created:
                dt = datetime.fromtimestamp(created / 1000)
                monthly_counts[dt.strftime("%Y-%m")] += 1

        return {
            "tag": tag,
            "total": total,
            "from_date": from_date,
            "to_date": to_date,
            "by_status": dict(sorted(status_counts.items(), key=lambda x: x[1], reverse=True)),
            "by_assignee": dict(sorted(assignee_counts.items(), key=lambda x: x[1], reverse=True)),
            "by_project": dict(sorted(project_counts.items(), key=lambda x: x[1], reverse=True)),
            "by_month": dict(sorted(monthly_counts.items())),
            "issues": issues,
        }


# =============================================================================
# CLI formatters
# =============================================================================

def print_issue(issue: dict):
    """Print issue details in human-readable format."""
    if "error" in issue:
        print(f"Error: {issue['error']}")
        return

    issue_id = issue.get("idReadable", "-")
    summary = issue.get("summary", "-")
    cf = issue.get("customFields", [])

    status = extract_field(cf, "Статус")
    assignee = extract_field(cf, "Assignee")
    priority = extract_field(cf, "Priority")
    region = extract_field(cf, "Регион")
    issue_type = extract_field(cf, "Type")

    tags = ", ".join(t.get("name", "") for t in issue.get("tags", [])) or "-"
    created = format_timestamp(issue.get("created"))
    updated = format_timestamp(issue.get("updated"))
    resolved = format_timestamp(issue.get("resolved"))
    description = issue.get("description") or ""

    print(f"\n{'='*60}")
    print(f"  {issue_id}: {summary}")
    print(f"{'='*60}")
    print(f"  Status:    {status}")
    print(f"  Assignee:  {assignee}")
    print(f"  Priority:  {priority}")
    print(f"  Type:      {issue_type}")
    print(f"  Region:    {region}")
    print(f"  Tags:      {tags}")
    print(f"  Created:   {created}")
    print(f"  Updated:   {updated}")
    if resolved != "-":
        print(f"  Resolved:  {resolved}")
    if description:
        print(f"\n  Description:")
        for line in description.split("\n"):
            print(f"    {line}")
    print()


def print_comments(issue_id: str, comments: list):
    """Print comments for an issue."""
    if not comments:
        print(f"\n{issue_id}: no comments")
        return

    count = len(comments)
    print(f"\n{issue_id} — {count} comment(s):")
    print("-" * 60)

    for comment in comments:
        author = comment.get("author", {}).get("fullName", "Unknown")
        created = format_timestamp(comment.get("created"))
        text = comment.get("text", "")
        # Truncate long comments for summary
        preview = " ".join(text.split())
        if len(preview) > 200:
            preview = preview[:197] + "..."

        print(f"  [{created}] {author}:")
        print(f"    {preview}")
        print()


def print_search_results(issues: list):
    """Print search results as a table."""
    if not issues:
        print("No issues found.")
        return

    print(f"\nFound {len(issues)} issue(s):")
    print(f"{'ID':<12} {'Status':<15} {'Assignee':<25} {'Summary'}")
    print("-" * 100)

    for issue in issues:
        issue_id = issue.get("idReadable", "-")
        summary = issue.get("summary", "-")
        cf = issue.get("customFields", [])
        status = extract_field(cf, "Статус")
        assignee = extract_field(cf, "Assignee")

        if len(summary) > 50:
            summary = summary[:47] + "..."
        print(f"{issue_id:<12} {status:<15} {assignee:<25} {summary}")


def print_stats(stats: dict):
    """Print tag statistics in human-readable format."""
    tag = stats["tag"]
    total = stats["total"]

    if total == 0:
        print(f"\nNo issues found with tag '{tag}'.")
        return

    print(f"\n{'='*60}")
    print(f"STATISTICS FOR TAG '{tag.upper()}'")
    print(f"{'='*60}")

    period = f"from {stats['from_date']}" if stats.get("from_date") else "all time"
    if stats.get("to_date"):
        period += f" to {stats['to_date']}"
    print(f"Period: {period}")
    print(f"\nTOTAL ISSUES: {total}")

    if stats["by_project"]:
        print(f"\nBy project:")
        for project, count in stats["by_project"].items():
            print(f"   {project}: {count} ({count/total*100:.1f}%)")

    if stats["by_status"]:
        print(f"\nBy status:")
        for status, count in stats["by_status"].items():
            print(f"   {status}: {count} ({count/total*100:.1f}%)")

    if stats["by_assignee"]:
        print(f"\nBy assignee:")
        for assignee, count in stats["by_assignee"].items():
            print(f"   {assignee}: {count} ({count/total*100:.1f}%)")

    if stats["by_month"]:
        print(f"\nBy month:")
        for month, count in stats["by_month"].items():
            print(f"   {month}: {count}")


# =============================================================================
# CLI
# =============================================================================

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="YouTrack CLI Client",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Common parent parser for --json flag
    json_parent = argparse.ArgumentParser(add_help=False)
    json_parent.add_argument("--json", action="store_true", help="Output as JSON")

    # info
    p_info = subparsers.add_parser("info", help="Get issue details", parents=[json_parent])
    p_info.add_argument("issue_id", help="Issue ID (e.g., TMK-824)")

    # comments
    p_comments = subparsers.add_parser("comments", help="Get issue comments", parents=[json_parent])
    p_comments.add_argument("issue_id", help="Issue ID")

    # comment (add)
    p_comment = subparsers.add_parser("comment", help="Add a comment to an issue", parents=[json_parent])
    p_comment.add_argument("issue_id", help="Issue ID")
    p_comment.add_argument("text", help="Comment text")

    # search
    p_search = subparsers.add_parser("search", help="Search issues", parents=[json_parent])
    p_search.add_argument("query", help="YouTrack search query")
    p_search.add_argument("--top", type=int, default=None, help="Max results (default: 500)")

    # create
    p_create = subparsers.add_parser("create", help="Create a new issue", parents=[json_parent])
    p_create.add_argument("project", help="Project short name (e.g., TMK)")
    p_create.add_argument("summary", help="Issue summary")
    p_create.add_argument("--description", "-d", help="Issue description")
    p_create.add_argument("--assignee", "-a", help="Assignee login")
    p_create.add_argument("--region", "-r", help="Region name")
    p_create.add_argument("--type", "-t", dest="issue_type", help="Issue Type (Task/Bug/Epic/...)")
    p_create.add_argument(
        "--field", "-f", dest="fields", action="append", default=[],
        metavar="NAME=VALUE",
        help="Extra custom field, repeatable. E.g. -f 'Контур=ХМАО: Рабочий контур'",
    )

    # update
    p_update = subparsers.add_parser("update", help="Update issue via command", parents=[json_parent])
    p_update.add_argument("issue_id", help="Issue ID")
    p_update.add_argument("--status", help="Set status")
    p_update.add_argument("--assignee", help="Set assignee login")
    p_update.add_argument("--tag", help="Add tag")
    p_update.add_argument("--cmd", "-c", dest="raw_command", help="Raw YouTrack command string")

    # stats
    p_stats = subparsers.add_parser("stats", help="Tag statistics", parents=[json_parent])
    p_stats.add_argument("--tag", default="ai", help="Tag to analyze (default: ai)")
    p_stats.add_argument("--from", dest="from_date", default="2026-01-01", help="Start date YYYY-MM-DD")
    p_stats.add_argument("--to", dest="to_date", default=None, help="End date YYYY-MM-DD")
    p_stats.add_argument("--list", action="store_true", help="Also print issue list")
    p_stats.add_argument("--limit", type=int, default=20, help="Issue list limit (default: 20)")

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    try:
        client = YouTrackClient()
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # ----- info -----
    if args.command == "info":
        issue = client.get_issue(args.issue_id)
        if args.json:
            print_json(issue)
        else:
            print_issue(issue)

    # ----- comments -----
    elif args.command == "comments":
        comments = client.get_comments(args.issue_id)
        if args.json:
            print_json(comments)
        else:
            print_comments(args.issue_id, comments)

    # ----- comment (add) -----
    elif args.command == "comment":
        result = client.add_comment(args.issue_id, args.text)
        if args.json:
            print_json(result)
        else:
            if isinstance(result, dict) and "error" in result:
                print(f"Error: {result['error']}")
                sys.exit(1)
            comment_id = result.get("id", "?")
            print(f"Comment added to {args.issue_id} (ID: {comment_id})")

    # ----- search -----
    elif args.command == "search":
        issues = client.search_issues(args.query, top=args.top)
        if args.json:
            print_json(issues)
        else:
            print_search_results(issues)

    # ----- create -----
    elif args.command == "create":
        extra_fields = {}
        for pair in args.fields:
            if "=" not in pair:
                print(f"Error: --field expects NAME=VALUE, got '{pair}'", file=sys.stderr)
                sys.exit(1)
            k, v = pair.split("=", 1)
            extra_fields[k.strip()] = v.strip()
        result = client.create_issue(
            project_id=args.project,
            summary=args.summary,
            description=args.description,
            assignee=args.assignee,
            region=args.region,
            issue_type=args.issue_type,
            extra_fields=extra_fields or None,
        )
        if args.json:
            print_json(result)
        else:
            if isinstance(result, dict) and "error" in result:
                print(f"Error: {result['error']}")
                if result.get("detail"):
                    print(f"Detail: {result['detail']}")
                sys.exit(1)
            issue_id = result.get("idReadable", "?")
            print(f"Created: {issue_id} — {result.get('summary', '')}")

    # ----- update -----
    elif args.command == "update":
        parts = []
        if args.status:
            parts.append(f"Статус {args.status}")
        if args.assignee:
            parts.append(f"Assignee {args.assignee}")
        if args.tag:
            parts.append(f"tag {args.tag}")
        if args.raw_command:
            parts.append(args.raw_command)

        if not parts:
            print("Error: specify at least one of --status, --assignee, --tag, or --cmd", file=sys.stderr)
            sys.exit(1)

        command_str = " ".join(parts)
        result = client.execute_command(args.issue_id, command_str)
        if args.json:
            print_json(result)
        else:
            if isinstance(result, dict) and "error" in result:
                print(f"Error: {result['error']}")
                sys.exit(1)
            print(f"Command executed on {args.issue_id}: {command_str}")

    # ----- stats -----
    elif args.command == "stats":
        stats = client.get_tag_stats(
            tag=args.tag,
            from_date=args.from_date,
            to_date=args.to_date,
        )

        if args.json:
            # Remove issues list for cleaner JSON stats output
            json_stats = {k: v for k, v in stats.items() if k != "issues"}
            print_json(json_stats)
        else:
            print_stats(stats)

            if args.list:
                issues = stats["issues"]
                limit = args.limit
                print(f"\n{'='*60}")
                print(f"ISSUE LIST (showing {min(len(issues), limit)} of {len(issues)})")
                print(f"{'='*60}")
                print(f"{'ID':<12} {'Date':<12} {'Status':<15} {'Summary'}")
                print("-" * 80)

                for issue in issues[:limit]:
                    iid = issue.get("idReadable", "-")
                    summary = issue.get("summary", "-")
                    cf = issue.get("customFields", [])
                    status = extract_field(cf, "Статус")
                    created = format_date(issue.get("created"))
                    if len(summary) > 50:
                        summary = summary[:47] + "..."
                    print(f"{iid:<12} {created:<12} {status:<15} {summary}")

                if len(issues) > limit:
                    print(f"\n... and {len(issues) - limit} more")


if __name__ == "__main__":
    main()
