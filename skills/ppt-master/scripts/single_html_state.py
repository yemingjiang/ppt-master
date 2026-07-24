#!/usr/bin/env python3
"""Track scaffold and export lineage for single-file HTML presentations."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any


STATE_SCHEMA_VERSION = 1
STATE_RELATIVE_PATH = Path("html_output") / ".ppt-master-state.json"


class StateError(ValueError):
    """Raised when the single-HTML lineage state is malformed."""


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_text(payload: str) -> str:
    return sha256_bytes(payload.encode("utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def state_path(project_path: Path) -> Path:
    return project_path.resolve() / STATE_RELATIVE_PATH


def empty_state(source: str = "output") -> dict[str, Any]:
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "source": source,
        "inputs": {},
        "slides": {},
        "managed_files": {},
        "export": {},
    }


def load_state(project_path: Path) -> dict[str, Any] | None:
    path = state_path(project_path)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise StateError(
            f"single-HTML state contains invalid JSON at line {error.lineno}: {path}"
        ) from error
    if not isinstance(payload, dict):
        raise StateError(f"single-HTML state must be a JSON object: {path}")
    if payload.get("schema_version") != STATE_SCHEMA_VERSION:
        raise StateError(
            f"unsupported single-HTML state schema {payload.get('schema_version')!r}: {path}"
        )
    if not isinstance(payload.get("slides"), dict):
        raise StateError(f"single-HTML state slides must be an object: {path}")
    if not isinstance(payload.get("inputs", {}), dict):
        raise StateError(f"single-HTML state inputs must be an object: {path}")
    if not isinstance(payload.get("managed_files"), dict):
        raise StateError(f"single-HTML state managed_files must be an object: {path}")
    if not isinstance(payload.get("export"), dict):
        raise StateError(f"single-HTML state export must be an object: {path}")
    return payload


def save_state(project_path: Path, state: dict[str, Any]) -> Path:
    path = state_path(project_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return path


def relative_path(project_path: Path, path: Path) -> str:
    resolved_project = project_path.resolve()
    resolved_path = path.resolve()
    try:
        return resolved_path.relative_to(resolved_project).as_posix()
    except ValueError as error:
        raise StateError(f"state path must remain inside the project: {resolved_path}") from error


def inspect_source_state(project_path: Path) -> dict[str, Any]:
    project_path = project_path.resolve()
    state = load_state(project_path)
    if state is None or not state["slides"]:
        return {
            "state": "untracked",
            "stale_slides": [],
            "conflicted_slides": [],
            "customized_slides": [],
            "missing_slides": [],
            "stale_inputs": [],
            "untracked_slides": [],
            "state_file": str(state_path(project_path)),
        }

    stale: list[str] = []
    conflicted: list[str] = []
    customized: list[str] = []
    missing: list[str] = []
    stale_inputs: list[str] = []
    tracked_source_files: set[str] = set()
    for slide_id, raw_entry in sorted(state["slides"].items()):
        if not isinstance(raw_entry, dict):
            raise StateError(f"single-HTML state slide {slide_id!r} must be an object")
        source_file = raw_entry.get("source_file")
        fragment_file = raw_entry.get("fragment_file")
        source_hash = raw_entry.get("source_sha256")
        managed_hash = raw_entry.get("managed_fragment_sha256")
        if not all(isinstance(item, str) and item for item in (
            source_file,
            fragment_file,
            source_hash,
            managed_hash,
        )):
            raise StateError(f"single-HTML state slide {slide_id!r} is incomplete")

        source_path = project_path / source_file
        fragment_path = project_path / fragment_file
        tracked_source_files.add(source_file)
        if not source_path.exists() or not fragment_path.exists():
            missing.append(str(slide_id))
            continue
        source_changed = sha256_file(source_path) != source_hash
        fragment_customized = sha256_file(fragment_path) != managed_hash
        if source_changed and fragment_customized:
            conflicted.append(str(slide_id))
        elif source_changed:
            stale.append(str(slide_id))
        elif fragment_customized:
            customized.append(str(slide_id))

    source_directory = {
        "output": "svg_output",
        "final": "svg_final",
    }.get(str(state.get("source")), "svg_output")
    current_source_files = {
        relative_path(project_path, path)
        for path in (project_path / source_directory).glob("*.svg")
    }
    untracked_slides = sorted(current_source_files - tracked_source_files)
    if tracked_source_files - current_source_files:
        for missing_source in sorted(tracked_source_files - current_source_files):
            missing_id = Path(missing_source).stem.split("_", 1)[0]
            if missing_id not in missing:
                missing.append(missing_id)

    for input_file, expected_hash in sorted(state.get("inputs", {}).items()):
        input_path = project_path / input_file
        if not input_path.exists() or sha256_file(input_path) != expected_hash:
            stale_inputs.append(input_file)

    if conflicted:
        status = "conflict"
    elif stale or missing or stale_inputs or untracked_slides:
        status = "stale"
    else:
        status = "current"
    return {
        "state": status,
        "stale_slides": stale,
        "conflicted_slides": conflicted,
        "customized_slides": customized,
        "missing_slides": missing,
        "stale_inputs": stale_inputs,
        "untracked_slides": untracked_slides,
        "state_file": str(state_path(project_path)),
    }


def inspect_export_state(
    project_path: Path,
    *,
    planned_document: str,
    output_path: Path,
) -> dict[str, Any]:
    project_path = project_path.resolve()
    output_path = output_path.resolve()
    planned_hash = sha256_text(planned_document)
    if not output_path.exists():
        export_state = "missing"
        output_hash = None
    else:
        output_hash = sha256_file(output_path)
        export_state = "current" if output_hash == planned_hash else "stale"
    return {
        "state": export_state,
        "planned_document_sha256": planned_hash,
        "output_sha256": output_hash,
        "output_html": str(output_path),
    }


def record_export(
    project_path: Path,
    *,
    planned_document: str,
    output_path: Path,
) -> dict[str, Any]:
    project_path = project_path.resolve()
    state = load_state(project_path) or empty_state()
    record = inspect_export_state(
        project_path,
        planned_document=planned_document,
        output_path=output_path,
    )
    try:
        output_file = relative_path(project_path, output_path)
    except StateError:
        output_file = str(output_path.resolve())
    state["export"] = {
        "output_file": output_file,
        "planned_document_sha256": record["planned_document_sha256"],
        "output_sha256": record["output_sha256"],
    }
    save_state(project_path, state)
    return record


def record_managed_fragment(
    project_path: Path,
    fragment_path: Path,
    *,
    media_profile: str | None = None,
    media_target: str | None = None,
) -> None:
    project_path = project_path.resolve()
    state = load_state(project_path)
    if state is None:
        return
    fragment_file = relative_path(project_path, fragment_path)
    for entry in state["slides"].values():
        if isinstance(entry, dict) and entry.get("fragment_file") == fragment_file:
            entry["managed_fragment_sha256"] = sha256_file(fragment_path)
            if media_profile:
                entry["media_profile"] = media_profile
            if media_target:
                entry["media_target"] = media_target
            save_state(project_path, state)
            return
