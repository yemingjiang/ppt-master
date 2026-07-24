#!/usr/bin/env python3
"""Check project text sources against an optional terminology policy."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any


DEFAULT_PATTERNS = (
    "main_content.md",
    "design_spec.md",
    "style_sheet.md",
    "asset_manifest.md",
    "notes/**/*.md",
    "svg_output/*.svg",
    "svg_final/*.svg",
    "html_output/slides/*.html",
)


class TerminologyError(ValueError):
    """Raised when the terminology policy cannot be applied."""


def load_policy(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise TerminologyError(
            f"terminology policy contains invalid JSON at line {error.lineno}: {path}"
        ) from error
    if not isinstance(payload, dict):
        raise TerminologyError(f"terminology policy must be a JSON object: {path}")
    forbidden = payload.get("forbidden", {})
    if not isinstance(forbidden, dict) or not all(
        isinstance(key, str)
        and key
        and isinstance(value, str)
        and value
        for key, value in forbidden.items()
    ):
        raise TerminologyError(
            "terminology policy 'forbidden' must map non-empty strings to replacements"
        )
    include = payload.get("include", list(DEFAULT_PATTERNS))
    if not isinstance(include, list) or not all(
        isinstance(pattern, str) and pattern for pattern in include
    ):
        raise TerminologyError("terminology policy 'include' must be an array of glob strings")
    return {
        "forbidden": forbidden,
        "include": include,
        "case_sensitive": bool(payload.get("case_sensitive", True)),
    }


def _matched_files(project_path: Path, patterns: list[str]) -> list[Path]:
    matched: set[Path] = set()
    for pattern in patterns:
        for path in project_path.glob(pattern):
            if path.is_file():
                matched.add(path.resolve())
    return sorted(matched)


def check_terminology(
    project_path: Path,
    *,
    config_path: Path | None = None,
) -> dict[str, object]:
    project_path = project_path.resolve()
    config_path = (
        config_path.resolve()
        if config_path is not None
        else (project_path / "terminology.json").resolve()
    )
    if not config_path.exists():
        return {
            "status": "not_configured",
            "project_path": str(project_path),
            "config": str(config_path),
            "files_checked": 0,
            "issue_count": 0,
            "issues": [],
        }

    policy = load_policy(config_path)
    files = _matched_files(project_path, policy["include"])
    issues: list[dict[str, object]] = []
    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as error:
            raise TerminologyError(f"expected UTF-8 text file: {path}") from error
        haystack = text if policy["case_sensitive"] else text.casefold()
        for forbidden, replacement in policy["forbidden"].items():
            needle = forbidden if policy["case_sensitive"] else forbidden.casefold()
            start = 0
            while True:
                index = haystack.find(needle, start)
                if index < 0:
                    break
                line = text.count("\n", 0, index) + 1
                line_start = text.rfind("\n", 0, index) + 1
                issues.append(
                    {
                        "file": path.relative_to(project_path).as_posix(),
                        "line": line,
                        "column": index - line_start + 1,
                        "found": text[index : index + len(forbidden)],
                        "replacement": replacement,
                    }
                )
                start = index + max(1, len(needle))
    return {
        "status": "issues" if issues else "ok",
        "project_path": str(project_path),
        "config": str(config_path),
        "files_checked": len(files),
        "issue_count": len(issues),
        "issues": issues,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check ppt-master project text against an optional terminology.json policy.",
        epilog=(
            "Examples:\n"
            "  python3 check_terminology.py projects/quarterly-review --json\n"
            "  python3 check_terminology.py projects/quarterly-review "
            "--config projects/quarterly-review/terminology.json --json\n\n"
            'Policy example: {"forbidden":{"XGU":"XGUI","Flow":"工作流"}}'
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("project_path", type=Path, help="Presentation project directory.")
    parser.add_argument(
        "--config",
        type=Path,
        help="Policy path; defaults to <project_path>/terminology.json.",
    )
    parser.add_argument("--json", action="store_true", help="Print one JSON object to stdout.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = check_terminology(args.project_path, config_path=args.config)
    except (OSError, TerminologyError, ValueError) as error:
        if args.json:
            print(json.dumps({"status": "error", "error": str(error)}, ensure_ascii=False))
        else:
            print(f"Error: {error}", file=os.sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    else:
        print(f"Status: {result['status']}")
        print(f"Files checked: {result['files_checked']}")
        print(f"Issues: {result['issue_count']}")
        for issue in result["issues"]:
            print(
                f"{issue['file']}:{issue['line']}:{issue['column']}: "
                f"{issue['found']} -> {issue['replacement']}"
            )
    return 2 if result["status"] == "issues" else 0


if __name__ == "__main__":
    raise SystemExit(main())
