#!/usr/bin/env python3
"""Tests for the capped download helper in backend_common."""

from pathlib import Path
import sys
import unittest


SCRIPT_DIR = Path(__file__).resolve().parent.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from image_backends import backend_common as bc  # noqa: E402


class _FakeResponse:
    def __init__(self, chunks, headers=None):
        self._chunks = chunks
        self.headers = headers or {}

    def iter_content(self, chunk_size=65536):
        for c in self._chunks:
            yield c


class ReadCappedTests(unittest.TestCase):
    def test_reads_small_body(self) -> None:
        resp = _FakeResponse([b"abc", b"def"])
        self.assertEqual(bc._read_capped(resp, max_bytes=100), b"abcdef")

    def test_rejects_oversized_content_length_header(self) -> None:
        resp = _FakeResponse([b"x"], headers={"Content-Length": str(10**9)})
        with self.assertRaises(ValueError):
            bc._read_capped(resp, max_bytes=1024)

    def test_rejects_when_stream_exceeds_cap_despite_missing_header(self) -> None:
        # No Content-Length, but the streamed body blows past the cap.
        resp = _FakeResponse([b"x" * 600, b"x" * 600])
        with self.assertRaises(ValueError):
            bc._read_capped(resp, max_bytes=1000)

    def test_lying_content_length_still_capped_by_stream(self) -> None:
        resp = _FakeResponse([b"x" * 2048], headers={"Content-Length": "1"})
        with self.assertRaises(ValueError):
            bc._read_capped(resp, max_bytes=1000)


class DownloadImageSchemeTests(unittest.TestCase):
    def test_rejects_file_scheme(self) -> None:
        with self.assertRaises(ValueError):
            bc.download_image("file:///etc/passwd", "/tmp/out.png")

    def test_rejects_non_http_scheme(self) -> None:
        with self.assertRaises(ValueError):
            bc.download_image("ftp://example.com/x.png", "/tmp/out.png")


class RunWithRetriesTests(unittest.TestCase):
    def test_returns_value_on_first_success(self) -> None:
        calls = []

        def once():
            calls.append(1)
            return "ok"

        self.assertEqual(bc.run_with_retries(once, max_retries=3), "ok")
        self.assertEqual(len(calls), 1)

    def test_fatal_error_not_retried(self) -> None:
        calls = []

        def once():
            calls.append(1)
            raise ValueError("unsupported aspect ratio")

        with self.assertRaises(ValueError):
            bc.run_with_retries(once, max_retries=3)
        self.assertEqual(len(calls), 1, "ValueError must not be retried")

    def test_transient_error_retried_then_succeeds(self) -> None:
        calls = []

        def once():
            calls.append(1)
            if len(calls) < 2:
                raise RuntimeError("429 rate limit")
            return "ok"

        # max_retries small; rate-limit delay would sleep, so patch sleep.
        original_sleep = bc.time.sleep
        bc.time.sleep = lambda *_: None
        try:
            result = bc.run_with_retries(once, max_retries=3)
        finally:
            bc.time.sleep = original_sleep
        self.assertEqual(result, "ok")
        self.assertEqual(len(calls), 2)

    def test_exhaustion_raises_runtime_error(self) -> None:
        def once():
            raise RuntimeError("boom")

        original_sleep = bc.time.sleep
        bc.time.sleep = lambda *_: None
        try:
            with self.assertRaises(RuntimeError):
                bc.run_with_retries(once, max_retries=2)
        finally:
            bc.time.sleep = original_sleep


if __name__ == "__main__":
    unittest.main()
