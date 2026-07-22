"""Tests for validated inputs to the offline single-file HTML builder."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from base64 import b64decode, b64encode
from pathlib import Path

from bs4 import BeautifulSoup


SCRIPT_DIR = Path(__file__).parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from build_single_html import (
    OfflineResourcePackager,
    PackagingError,
    load_manifest,
    render_document,
    validate_slide_fragment,
)


MANIFEST = {
    "schema_version": 1,
    "title": "Offline Demo",
    "lang": "zh-CN",
    "aspect_ratio": "16 / 9",
    "theme": {
        "name": "executive-red",
        "tokens": {
            "background": "#FFFFFF",
            "surface": "#F2F2F2",
            "primary": "#B50F0A",
            "on_primary": "#FFFFFF",
            "text": "#222222",
            "muted": "#666666",
            "line": "#D7D7D7",
        },
    },
    "slides": [
        {"id": "01", "title": "封面", "file": "slides/01_cover.html", "notes_key": "01"},
        {"id": "02", "title": "概览", "file": "slides/02_overview.html", "notes_key": "02"},
    ],
}


class ProjectFixture(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project = Path(self.temp_dir.name)
        (self.project / "notes").mkdir()
        (self.project / "html_output" / "slides").mkdir(parents=True)
        (self.project / "design_spec.md").write_text("# Design", encoding="utf-8")
        (self.project / "notes" / "total.md").write_text("# Notes", encoding="utf-8")
        (self.project / "html_output" / "presentation.css").write_text("", encoding="utf-8")
        for slide in MANIFEST["slides"]:
            path = self.project / "html_output" / slide["file"]
            path.write_text(
                f'<section class="pm-slide" data-slide-id="{slide["id"]}"></section>',
                encoding="utf-8",
            )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def write_manifest(self, manifest: dict[str, object]) -> None:
        path = self.project / "html_output" / "presentation.json"
        path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")


class LoadManifestTests(ProjectFixture):
    def test_accepts_valid_manifest(self) -> None:
        self.write_manifest(MANIFEST)

        manifest = load_manifest(self.project)

        self.assertEqual(manifest["title"], "Offline Demo")

    def test_rejects_unsupported_schema_version(self) -> None:
        manifest = dict(MANIFEST, schema_version=2)
        self.write_manifest(manifest)

        with self.assertRaisesRegex(PackagingError, "schema_version"):
            load_manifest(self.project)

    def test_rejects_duplicate_slide_ids(self) -> None:
        manifest = dict(MANIFEST, slides=[*MANIFEST["slides"], dict(MANIFEST["slides"][0])])
        self.write_manifest(manifest)

        with self.assertRaisesRegex(PackagingError, "slides.*id"):
            load_manifest(self.project)

    def test_rejects_slide_path_outside_project(self) -> None:
        manifest = dict(MANIFEST)
        manifest["slides"] = [dict(MANIFEST["slides"][0], file="../../outside.html")]
        self.write_manifest(manifest)

        with self.assertRaisesRegex(PackagingError, "slides.*file"):
            load_manifest(self.project)


class ValidateSlideFragmentTests(unittest.TestCase):
    def test_accepts_one_matching_slide_root(self) -> None:
        source = Path("slides/01_cover.html")

        fragment = validate_slide_fragment(
            '<section class="pm-slide" data-slide-id="01"><h1>Title</h1></section>',
            "01",
            source,
        )

        self.assertEqual(
            fragment,
            '<section class="pm-slide" data-slide-id="01"><h1>Title</h1></section>',
        )

    def test_rejects_missing_or_nonmatching_slide_root(self) -> None:
        with self.assertRaisesRegex(PackagingError, "slide root"):
            validate_slide_fragment('<div class="pm-slide" data-slide-id="01"></div>', "01", Path("x"))

        with self.assertRaisesRegex(PackagingError, "data-slide-id"):
            validate_slide_fragment('<section class="pm-slide" data-slide-id="02"></section>', "01", Path("x"))

    def test_rejects_multiple_slide_roots(self) -> None:
        with self.assertRaisesRegex(PackagingError, "exactly one"):
            validate_slide_fragment(
                '<section class="pm-slide" data-slide-id="01"></section>'
                '<section class="pm-slide" data-slide-id="01"></section>',
                "01",
                Path("x"),
            )

    def test_rejects_a_slide_section_inside_a_wrapper(self) -> None:
        with self.assertRaisesRegex(PackagingError, "slide root"):
            validate_slide_fragment(
                '<div><section class="pm-slide" data-slide-id="01"></section></div>',
                "01",
                Path("x"),
            )

    def test_rejects_stray_top_level_text(self) -> None:
        with self.assertRaisesRegex(PackagingError, "slide root"):
            validate_slide_fragment(
                'stray text<section class="pm-slide" data-slide-id="01"></section>',
                "01",
                Path("x"),
            )

    def test_allows_top_level_whitespace_and_comments(self) -> None:
        fragment = validate_slide_fragment(
            ' \n<!-- source marker -->\n<section class="pm-slide" data-slide-id="01"></section>\n',
            "01",
            Path("x"),
        )

        self.assertEqual(fragment, '<section class="pm-slide" data-slide-id="01"></section>')

    def test_rejects_scripts(self) -> None:
        with self.assertRaisesRegex(PackagingError, "script"):
            validate_slide_fragment(
                '<section class="pm-slide" data-slide-id="01"><script>bad()</script></section>',
                "01",
                Path("x"),
            )


class RenderDocumentRuntimeContractTests(unittest.TestCase):
    def render(self) -> str:
        slides = [
            '<section class="pm-slide" data-slide-id="01">Cover</section>',
            '<section class="pm-slide" data-slide-id="02">Overview</section>',
        ]
        notes = {"01": {"script": "Opening notes"}, "02": {"script": "Closing notes"}}
        return render_document(MANIFEST, slides, ".slide-01 { color: red; }", notes)

    def test_renders_stable_presentation_shell_hooks(self) -> None:
        document = self.render()

        for hook in (
            'data-pm-action="previous"',
            'data-pm-action="next"',
            'data-pm-action="fullscreen"',
            'data-pm-action="notes"',
            'id="pmNotesPanel"',
            'id="pmProgress"',
            "prefers-reduced-motion",
        ):
            self.assertIn(hook, document)

    def test_runtime_script_parses_in_node_and_has_navigation_contract(self) -> None:
        document = self.render()
        runtime = BeautifulSoup(document, "html.parser").find_all("script")[-1].get_text()

        result = subprocess.run(
            ["node", "-e", "const vm = require('vm'); new vm.Script(process.argv[1]);", runtime],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        for behavior in (
            "ArrowLeft",
            "ArrowRight",
            "PageUp",
            "PageDown",
            "Space",
            "Home",
            "End",
            "case \"f\"",
            "case \"n\"",
            "pointerdown",
            "pointerup",
            "touchstart",
            "touchend",
            "isInteractiveTarget",
            "location.hash",
            "pauseInactiveMedia",
            "controls",
        ):
            self.assertIn(behavior, runtime)

    def test_embeds_notes_without_allowing_script_termination(self) -> None:
        document = render_document(
            MANIFEST,
            ['<section class="pm-slide" data-slide-id="01">Cover</section>'],
            "",
            {"01": {"script": "</script><script>unsafe()</script>"}},
        )

        self.assertIn('<\\/script>', document)
        self.assertNotIn('</script><script>unsafe()', document)

    def run_runtime_probe(self, hash_value: str, probe: str = "") -> subprocess.CompletedProcess[str]:
        runtime = BeautifulSoup(self.render(), "html.parser").find_all("script")[-1].get_text()
        runner = r'''
const vm = require("vm");
const listeners = {};
const timerCallbacks = new Map();
let nextTimer = 1;
function register(name, type, handler) {
  (listeners[name] ||= {})[type] = handler;
}
function classList() {
  const values = new Set();
  return { add: (value) => values.add(value), remove: (value) => values.delete(value), contains: (value) => values.has(value), toggle: (value, force) => force ? values.add(value) : values.delete(value) };
}
function node(name, extra = {}) {
  return Object.assign({
    classList: classList(), dataset: {}, style: {}, textContent: "", hidden: false,
    addEventListener(type, handler) { register(name, type, handler); },
    querySelectorAll() { return []; }, querySelector() { return controlButton; },
    setAttribute() {}, closest() { return null; }, focus() { activeElement = this; },
  }, extra);
}
const controlButton = node("controlButton");
const app = node("app");
const stage = node("stage");
const slideOne = node("slideOne", { dataset: { slideId: "01" } });
const deck = node("deck", { querySelectorAll() { return [slideOne]; } });
const notesCloseButton = node("notesCloseButton", { dataset: { pmAction: "notes" } });
const controls = node("controls", { querySelector() { return controlButton; } });
const pageCount = node("pageCount");
const progress = node("progress");
const notesPanel = node("notesPanel", { hidden: true, querySelector() { return notesCloseButton; } });
const notesContent = node("notesContent");
const notesData = node("notesData", { textContent: "{}" });
let activeElement = null;
controlButton.dataset.pmAction = "notes";
controlButton.closest = (selector) => selector.includes("[data-pm-action]") ? controlButton : (selector.includes("pmControls") ? controls : null);
notesCloseButton.closest = (selector) => selector.includes("[data-pm-action]") ? notesCloseButton : (selector.includes("pmNotesPanel") ? notesPanel : null);
const elements = { pmApp: app, pmStage: stage, pmDeck: deck, pmControls: controls, pmPageCount: pageCount, pmProgress: progress, pmNotesPanel: notesPanel, pmNotesContent: notesContent, pmNotesData: notesData };
const document = {
  fullscreenElement: null,
  get activeElement() { return activeElement; }, set activeElement(value) { activeElement = value; },
  getElementById(id) { return elements[id]; },
  addEventListener(type, handler) { register("document", type, handler); },
};
const window = {
  location: { hash: process.argv[2] },
  addEventListener(type, handler) { register("window", type, handler); },
  setTimeout(handler) { const id = nextTimer++; timerCallbacks.set(id, handler); return id; },
  clearTimeout(id) { timerCallbacks.delete(id); },
};
const history = { replaceState(_state, _title, hash) { window.location.hash = hash; } };
const context = { document, window, history, app, stage, controls, controlButton, notesCloseButton, notesPanel, slideOne, listeners, timerCallbacks };
vm.createContext(context);
new vm.Script(process.argv[1]).runInContext(context);
if (process.argv[3]) new vm.Script(process.argv[3]).runInContext(context);
'''
        return subprocess.run(
            ["node", "-e", runner, runtime, hash_value, probe],
            check=False,
            capture_output=True,
            text=True,
        )

    def test_malformed_hash_does_not_crash_runtime_startup(self) -> None:
        result = self.run_runtime_probe(
            "#%",
            "if (!slideOne.classList.contains('pm-active')) throw new Error('slide one was not activated');"
            "if (window.location.hash !== '#01') throw new Error('malformed hash was not normalized');",
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_closing_notes_returns_focus_to_notes_trigger(self) -> None:
        result = self.run_runtime_probe(
            "",
            "listeners.document.click({ target: controlButton, preventDefault() {} });"
            "if (document.activeElement !== notesCloseButton) throw new Error('notes close control was not focused');"
            "listeners.document.click({ target: notesCloseButton, preventDefault() {} });"
            "if (document.activeElement !== controlButton) throw new Error('notes trigger did not regain focus');",
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_controls_remain_visible_while_focus_is_inside_controls(self) -> None:
        result = self.run_runtime_probe(
            "",
            "document.activeElement = controlButton; [...timerCallbacks.values()].at(-1)();"
            "if (app.classList.contains('pm-controls-hidden')) throw new Error('controls hidden with focus');",
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_stage_pointerdown_reveals_hidden_controls(self) -> None:
        result = self.run_runtime_probe(
            "",
            "app.classList.add('pm-controls-hidden');"
            "listeners.stage.pointerdown({ pointerType: 'mouse', clientX: 10, target: stage });"
            "if (app.classList.contains('pm-controls-hidden')) throw new Error('stage pointer did not reveal controls');",
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_rejects_non_color_theme_token_values(self) -> None:
        manifest = json.loads(json.dumps(MANIFEST))
        manifest["theme"]["tokens"]["primary"] = "url(https://example.test/theme.css)"

        with self.assertRaisesRegex(PackagingError, r"theme\.tokens\.primary"):
            render_document(manifest, [], "", {})


class OfflineResourcePackagerTests(ProjectFixture):
    def setUp(self) -> None:
        super().setUp()
        self.images = self.project / "images"
        self.images.mkdir()
        self.chart = b"\x89PNG\r\n\x1a\nchart"
        self.poster = b"\x89PNG\r\n\x1a\nposter"
        self.video = b"mp4-demo"
        self.audio = b"mp3-demo"
        self.font = b"woff2-demo"
        (self.images / "chart.png").write_bytes(self.chart)
        (self.images / "poster.png").write_bytes(self.poster)
        (self.images / "demo.mp4").write_bytes(self.video)
        (self.images / "narration.mp3").write_bytes(self.audio)
        (self.images / "demo.woff2").write_bytes(self.font)
        self.slide_path = self.project / "html_output" / "slides" / "01_cover.html"

    def data_uri(self, media_type: str, contents: bytes) -> str:
        return f"data:{media_type};base64,{b64encode(contents).decode('ascii')}"

    def test_embeds_media_sources_and_css_resources(self) -> None:
        packager = OfflineResourcePackager(self.project)
        html = """
        <img src="../../images/chart.png">
        <video src="../../images/demo.mp4" poster="../../images/poster.png"></video>
        <audio src="../../images/narration.mp3"></audio>
        <source src="../../images/demo.mp4" type="video/mp4">
        <div style="background-image: url('../../images/chart.png')"></div>
        <style>@font-face { font-family: Demo; src: url("../../images/demo.woff2") format("woff2"); }
        .hero { background-image: url("../../images/chart.png"); }</style>
        """

        rewritten = packager.rewrite_html(html, self.slide_path)

        self.assertIn(self.data_uri("image/png", self.chart), rewritten)
        self.assertIn(self.data_uri("video/mp4", self.video), rewritten)
        self.assertIn(self.data_uri("image/png", self.poster), rewritten)
        self.assertIn(self.data_uri("audio/mpeg", self.audio), rewritten)
        self.assertIn(self.data_uri("font/woff2", self.font), rewritten)
        self.assertNotIn("../../images/", rewritten)
        self.assertEqual(packager.embedded_count, 8)

    def test_preserves_data_uris_and_fragment_urls(self) -> None:
        existing = "data:image/png;base64,already-embedded"
        packager = OfflineResourcePackager(self.project)
        html = (
            f'<img src="{existing}"><div style="filter: url(#gradient)"></div>'
            "<style>.mask { filter: url(#gradient); }</style>"
        )

        rewritten = packager.rewrite_html(html, self.slide_path)

        self.assertIn(existing, rewritten)
        self.assertIn("url(#gradient)", rewritten)
        self.assertEqual(packager.embedded_count, 0)

    def test_embeds_local_candidate_in_mixed_data_uri_srcset(self) -> None:
        existing = "data:image/svg+xml,%3Csvg%3E"
        packager = OfflineResourcePackager(self.project)

        rewritten = packager.rewrite_html(
            f'<img srcset="{existing} 1x, ../../images/chart.png 2x">', self.slide_path
        )

        self.assertIn(existing, rewritten)
        self.assertIn(f"{existing} 1x", rewritten)
        self.assertIn(f"{self.data_uri('image/png', self.chart)} 2x", rewritten)
        self.assertNotIn("../../images/chart.png", rewritten)

    def test_embeds_no_whitespace_srcset_candidate_after_data_uri_descriptor(self) -> None:
        existing = "data:image/png;base64,AAA"
        packager = OfflineResourcePackager(self.project)

        rewritten = packager.rewrite_html(
            f'<img srcset="{existing} 1x,../../images/chart.png 2x">', self.slide_path
        )

        self.assertIn(f"{existing} 1x", rewritten)
        self.assertIn(f"{self.data_uri('image/png', self.chart)} 2x", rewritten)
        self.assertNotIn("../../images/chart.png", rewritten)

    def test_recursively_inlines_local_css_imports_and_assets(self) -> None:
        styles = self.project / "styles"
        styles.mkdir()
        root_css = styles / "root.css"
        root_css.write_text('@import "nested.css"; @import url("also.css");', encoding="utf-8")
        (styles / "nested.css").write_text(
            '.nested { background: url("../images/chart.png"); }', encoding="utf-8"
        )
        (styles / "also.css").write_text(
            '.also { background: url("../images/chart.png"); }', encoding="utf-8"
        )
        packager = OfflineResourcePackager(self.project)

        rewritten = packager.rewrite_css(root_css.read_text(encoding="utf-8"), root_css)

        self.assertNotIn("@import", rewritten)
        self.assertNotIn("nested.css", rewritten)
        self.assertNotIn("also.css", rewritten)
        self.assertNotIn("../images/chart.png", rewritten)
        self.assertEqual(rewritten.count(self.data_uri("image/png", self.chart)), 2)

    def test_wraps_inlined_css_import_with_its_media_condition(self) -> None:
        styles = self.project / "styles"
        styles.mkdir()
        root_css = styles / "root.css"
        root_css.write_text('@import "print.css" print;', encoding="utf-8")
        (styles / "print.css").write_text(".print-only { display: block; }", encoding="utf-8")
        packager = OfflineResourcePackager(self.project)

        rewritten = packager.rewrite_css(root_css.read_text(encoding="utf-8"), root_css)

        self.assertTrue(rewritten.startswith("@media print {"))
        self.assertTrue(rewritten.endswith("}"))
        self.assertIn(".print-only { display: block; }", rewritten)
        self.assertNotIn("@import", rewritten)

    def test_rejects_css_import_cycles_with_ordered_paths(self) -> None:
        styles = self.project / "styles"
        styles.mkdir()
        root_css = styles / "a.css"
        root_css.write_text('@import "b.css";', encoding="utf-8")
        (styles / "b.css").write_text('@import url("a.css");', encoding="utf-8")
        packager = OfflineResourcePackager(self.project)

        with self.assertRaisesRegex(PackagingError, r"a\.css.*b\.css.*a\.css"):
            packager.rewrite_css(root_css.read_text(encoding="utf-8"), root_css)

    def test_rejects_remote_runtime_resources_and_css_imports(self) -> None:
        packager = OfflineResourcePackager(self.project)

        with self.assertRaisesRegex(PackagingError, "remote runtime"):
            packager.rewrite_html('<img src="https://example.test/chart.png">', self.slide_path)
        with self.assertRaisesRegex(PackagingError, "remote runtime"):
            packager.rewrite_css('@import url("https://example.test/theme.css");', self.slide_path)

    def test_rejects_project_escaping_resource_urls(self) -> None:
        packager = OfflineResourcePackager(self.project)

        with self.assertRaisesRegex(PackagingError, "stay inside the project"):
            packager.rewrite_html('<img src="../../../outside.png">', self.slide_path)

    def test_inlines_nested_iframe_documents_and_dependencies(self) -> None:
        interactive = self.project / "interactive"
        interactive.mkdir()
        (interactive / "root.css").write_text(
            '.root { background-image: url("../images/chart.png"); }', encoding="utf-8"
        )
        (interactive / "root.js").write_text("window.interactiveReady = true;", encoding="utf-8")
        (interactive / "child.html").write_text(
            '<html><body><img src="../images/chart.png"></body></html>', encoding="utf-8"
        )
        (interactive / "root.html").write_text(
            "<html><head><link rel=\"stylesheet\" href=\"root.css\"></head><body>"
            "<script src=\"root.js\"></script><iframe src=\"child.html\"></iframe>"
            "</body></html>",
            encoding="utf-8",
        )
        packager = OfflineResourcePackager(self.project)

        rewritten = packager.rewrite_html(
            '<iframe src="../../interactive/root.html"></iframe>', self.slide_path
        )

        outer = BeautifulSoup(rewritten, "html.parser").iframe
        root_html = b64decode(outer["src"].split(",", 1)[1]).decode("utf-8")
        self.assertNotIn("root.css", root_html)
        self.assertNotIn("root.js", root_html)
        self.assertNotIn("child.html", root_html)
        self.assertNotIn("../images/", root_html)
        self.assertIn("window.interactiveReady = true;", root_html)
        self.assertIn(self.data_uri("image/png", self.chart), root_html)

        nested = BeautifulSoup(root_html, "html.parser").iframe
        child_html = b64decode(nested["src"].split(",", 1)[1]).decode("utf-8")
        self.assertIn(self.data_uri("image/png", self.chart), child_html)
        self.assertNotIn("../images/", child_html)

    def test_rejects_nested_iframe_cycles_with_ordered_paths(self) -> None:
        interactive = self.project / "interactive"
        interactive.mkdir()
        (interactive / "a.html").write_text('<iframe src="b.html"></iframe>', encoding="utf-8")
        (interactive / "b.html").write_text('<iframe src="a.html"></iframe>', encoding="utf-8")
        packager = OfflineResourcePackager(self.project)

        with self.assertRaisesRegex(PackagingError, r"a\.html.*b\.html.*a\.html"):
            packager.rewrite_html(
                '<iframe src="../../interactive/a.html"></iframe>', self.slide_path
            )


if __name__ == "__main__":
    unittest.main()
