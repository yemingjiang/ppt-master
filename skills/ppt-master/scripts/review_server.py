#!/usr/bin/env python3
"""Serve a ppt-master preview with a writable review endpoint."""

from __future__ import annotations

import argparse
import json
from functools import partial
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from build_preview_html import render_preview
from main_content_pipeline import apply_comments_to_main_content


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Serve a ppt-master project for skeleton review. "
            "Supports in-browser comment application to main_content.md."
        ),
        epilog=(
            "Examples:\n"
            "  python3 scripts/review_server.py projects/demo\n"
            "  python3 scripts/review_server.py projects/demo --port 8010\n"
            "  python3 scripts/review_server.py projects/demo --source final --title \"Demo Review\""
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("project_path", help="Path to the ppt-master project directory.")
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Bind host. Default: 127.0.0.1",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Bind port. Default: 8000",
    )
    parser.add_argument(
        "--source",
        choices=("output", "final"),
        default="output",
        help="Preview source directory: svg_output or svg_final. Default: output.",
    )
    parser.add_argument(
        "--title",
        help="Optional preview title. Default: project name + draft review label.",
    )
    return parser.parse_args()


class ReviewServer(ThreadingHTTPServer):
    def __init__(
        self,
        server_address: tuple[str, int],
        handler_class,
        *,
        project_path: Path,
        default_source: str,
        default_title: str | None,
    ) -> None:
        self.project_path = project_path
        self.default_source = default_source
        self.default_title = default_title
        super().__init__(server_address, handler_class)


class ReviewRequestHandler(SimpleHTTPRequestHandler):
    server: ReviewServer

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def _send_json(self, payload: dict[str, object], status: int = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        if self.path.rstrip("/") != "/__ppt_master/update_main_content":
            self._send_json({"status": "error", "error": f"Unsupported endpoint: {self.path}"}, HTTPStatus.NOT_FOUND)
            return

        try:
            payload = self._read_json()
            comments = payload.get("comments") or {}
            if not isinstance(comments, dict):
                raise ValueError("`comments` must be a JSON object keyed by slide number.")

            source = payload.get("source") or self.server.default_source
            if source not in {"output", "final"}:
                raise ValueError("`source` must be `output` or `final`.")

            title = payload.get("title") or self.server.default_title
            result = apply_comments_to_main_content(self.server.project_path, comments)
            preview = render_preview(self.server.project_path, source=source, title=title)
            self._send_json(
                {
                    "status": "ok",
                    "project_path": str(self.server.project_path),
                    "main_content_path": result["main_content_path"],
                    "design_spec_path": result["design_spec_path"],
                    "asset_manifest_path": result["asset_manifest_path"],
                    "updated_slides": result["updated_slides"],
                    "review_note_counts": result["review_note_counts"],
                    "preview": preview,
                }
            )
        except Exception as error:  # pragma: no cover - runtime safety
            self._send_json({"status": "error", "error": str(error)}, HTTPStatus.BAD_REQUEST)

    def _read_json(self) -> dict[str, object]:
        content_length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(content_length) if content_length > 0 else b"{}"
        return json.loads(raw.decode("utf-8") or "{}")


def main() -> int:
    args = parse_args()
    project_path = Path(args.project_path).expanduser().resolve()
    if not project_path.exists():
        raise SystemExit(f"Error: project path does not exist: {project_path}")

    preview = render_preview(project_path, source=args.source, title=args.title)
    handler = partial(ReviewRequestHandler, directory=str(project_path))
    server = ReviewServer(
        (args.host, args.port),
        handler,
        project_path=project_path,
        default_source=args.source,
        default_title=args.title,
    )
    print(f"Serving: {preview['output_html']}")
    print(f"URL: http://{args.host}:{args.port}/preview/index.html")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
