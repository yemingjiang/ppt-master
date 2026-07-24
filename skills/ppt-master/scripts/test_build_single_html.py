"""Tests for validated inputs to the offline single-file HTML builder."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from base64 import b64decode, b64encode
from html import escape
from pathlib import Path
from unittest.mock import patch
from urllib.parse import quote

from bs4 import BeautifulSoup


SCRIPT_DIR = Path(__file__).parent
SKILL_DIR = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from build_single_html import (
    OfflineResourcePackager,
    PackagingError,
    _validate_offline_document,
    _write_atomically,
    build_single_html,
    check_single_html,
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


class HtmlPresentationDocumentationContractTests(unittest.TestCase):
    """Keep the agent-facing final-HTML workflow discoverable and unambiguous."""

    def test_primary_docs_name_the_final_html_contract(self) -> None:
        documents = (
            (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8"),
            (SKILL_DIR / "references" / "html-presentation.md").read_text(encoding="utf-8"),
            (SKILL_DIR / "templates" / "design_spec_reference.md").read_text(
                encoding="utf-8"
            ),
        )

        for required_text in (
            "Single-file HTML Presentation",
            "references/html-presentation.md",
            "scripts/build_single_html.py",
            "html_output/presentation.json",
            "exports/<project_name>.single.html",
        ):
            self.assertTrue(
                any(required_text in document for document in documents), required_text
            )

    def test_skill_routes_final_html_to_its_dedicated_reference(self) -> None:
        skill = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8").replace("**", "")

        self.assertIn("Single-file HTML Presentation", skill)
        self.assertIn("references/html-presentation.md", skill)
        self.assertIn("scripts/build_single_html.py", skill)
        self.assertIn("preview/index.html", skill)
        self.assertIn("is not the final HTML", skill)
        self.assertIn("Each run has exactly one Deliverable Mode.", skill)

    def test_html_reference_documents_source_and_delivery_contract(self) -> None:
        reference = (SKILL_DIR / "references" / "html-presentation.md").read_text(
            encoding="utf-8"
        )

        for required_text in (
            "html_output/presentation.json",
            "exports/<project_name>.single.html",
            "scripts/build_single_html.py",
            "pm-slide",
            "data-slide-id",
            "iframe",
            "speaker notes",
            "offline",
        ):
            self.assertIn(required_text, reference)

    def test_design_spec_records_html_mode_details(self) -> None:
        template = (SKILL_DIR / "templates" / "design_spec_reference.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("Single-file HTML Presentation", template)
        self.assertIn("HTML Presentation", template)
        self.assertIn("html_output/presentation.json", template)

    def test_skill_locks_review_gate_and_exclusive_final_routes(self) -> None:
        skill = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8").replace("**", "")

        for required_text in (
            "Each run has exactly one Deliverable Mode.",
            "Review Skeleton: stop after Step 7; do not select or produce a final target.",
            "Single-file HTML Presentation: run only the HTML branch.",
            "NEVER invoke Native Editable Handoff or Legacy Direct Export in that run.",
            "Native Editable Handoff: produce only the native editable PPTX.",
            "Legacy Direct Export: produce only the explicitly requested compatibility PPTX.",
            "Do not begin any final production before Step 7",
        ):
            self.assertIn(required_text, skill)

    def test_strategist_locks_mode_and_confirms_html_theme(self) -> None:
        strategist = (
            (SKILL_DIR / "references" / "strategist.md")
            .read_text(encoding="utf-8")
            .replace("**", "")
        )

        for required_text in (
            "Each run has exactly one Deliverable Mode.",
            "Review Skeleton: stop after Step 7 with no final target.",
            "Single-file HTML Presentation: final HTML only; do not invoke a PPTX path.",
            "Native Editable Handoff: final native editable PPTX only.",
            "Legacy Direct Export: explicit compatibility PPTX only.",
            "executive-red",
            "#FFFFFF, #F2F2F2, #B50F0A, #FFFFFF, #222222, #666666, #D7D7D7",
            "The user may override this theme before generation.",
        ):
            self.assertIn(required_text, strategist)

    def test_executor_locks_mode_specific_completion(self) -> None:
        executor = (
            (SKILL_DIR / "references" / "executor-base.md")
            .read_text(encoding="utf-8")
            .replace("**", "")
        )

        for required_text in (
            "Each run has exactly one Deliverable Mode.",
            "Review Skeleton: stop after Step 7 with no final target.",
            "Single-file HTML Presentation: package only the final offline HTML.",
            "Native Editable Handoff: package only the final native editable PPTX.",
            "Legacy Direct Export: package only the explicitly requested compatibility PPTX.",
        ):
            self.assertIn(required_text, executor)

    def test_html_reference_locks_theme_at_build_time(self) -> None:
        reference = (SKILL_DIR / "references" / "html-presentation.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("The confirmed theme is fixed at build time.", reference)
        self.assertIn("A runtime theme switcher or chooser is forbidden.", reference)

    def test_design_template_records_confirmed_html_theme_and_exclusive_mode(self) -> None:
        template = (SKILL_DIR / "templates" / "design_spec_reference.md").read_text(
            encoding="utf-8"
        )

        for required_text in (
            "Exactly One Deliverable Mode",
            "Review Skeleton: no final target",
            "Confirmed HTML Theme and Tokens",
            "executive-red",
            "#FFFFFF",
            "#F2F2F2",
            "#B50F0A",
            "#222222",
            "#666666",
            "#D7D7D7",
        ):
            self.assertIn(required_text, template)

    def test_entry_points_condition_native_rebuild_on_its_selected_mode(self) -> None:
        agents = (SKILL_DIR.parent.parent / "AGENTS.md").read_text(encoding="utf-8")
        readme = (SKILL_DIR.parent.parent / "README.md").read_text(encoding="utf-8")
        scripts_readme = (SCRIPT_DIR / "README.md").read_text(encoding="utf-8")

        for document in (agents, readme, scripts_readme):
            self.assertIn("Each run has exactly one Deliverable Mode.", document)
            self.assertIn("Review Skeleton: stop after Step 7 with no final target.", document)
        self.assertIn("Native Editable Handoff is selected", readme)
        self.assertIn("Native Editable Handoff is selected", scripts_readme)


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
            'data-pm-action="help"',
            'id="pmNotesPanel"',
            'id="pmHelpPanel"',
            'id="pmRuntimeData"',
            'id="pmProgress"',
            "prefers-reduced-motion",
        ):
            self.assertIn(hook, document)

    def test_localizes_runtime_shell_from_manifest_language(self) -> None:
        document = self.render()
        self.assertIn('aria-label="上一页"', document)
        self.assertIn(">演讲者备注<", document)
        self.assertIn(">键盘 / 翻页笔<", document)
        self.assertIn('"noNotes":"本页没有演讲者备注。"', document)

        english_manifest = json.loads(json.dumps(MANIFEST))
        english_manifest["lang"] = "en-US"
        english = render_document(
            english_manifest,
            ['<section class="pm-slide" data-slide-id="01">Cover</section>'],
            "",
            {},
        )
        self.assertIn('aria-label="Previous slide"', english)
        self.assertIn(">Speaker notes<", english)
        self.assertIn('"noNotes":"No speaker notes for this slide."', english)

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
            "ArrowUp",
            "ArrowDown",
            "PageUp",
            "PageDown",
            "Space",
            "Enter",
            "Backspace",
            "MediaTrackPrevious",
            "MediaTrackNext",
            "Home",
            "End",
            "case \"f\"",
            "case \"s\"",
            "case \"?\"",
            "pointerdown",
            "pointerup",
            "pointercancel",
            "touchstart",
            "touchend",
            "touchcancel",
            "\"wheel\"",
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
const slideTwo = node("slideTwo", { dataset: { slideId: "02" } });
const visibleSlideChild = node("visibleSlideChild");
const deck = node("deck", { querySelectorAll() { return [slideOne, slideTwo]; } });
const notesCloseButton = node("notesCloseButton", { dataset: { pmAction: "notes" } });
const helpButton = node("helpButton", { dataset: { pmAction: "help" } });
const helpCloseButton = node("helpCloseButton", { dataset: { pmAction: "help" } });
const controls = node("controls", { querySelector(selector) { return selector.includes('"help"') ? helpButton : controlButton; } });
const pageCount = node("pageCount");
const progress = node("progress");
const notesPanel = node("notesPanel", { id: "pmNotesPanel", hidden: true, querySelector() { return notesCloseButton; } });
const helpPanel = node("helpPanel", { id: "pmHelpPanel", hidden: true, querySelector() { return helpCloseButton; } });
const notesContent = node("notesContent");
const notesData = node("notesData", { textContent: "{}" });
const runtimeData = node("runtimeData", { textContent: '{"noNotes":"本页没有演讲者备注。"}' });
let activeElement = null;
controlButton.dataset.pmAction = "notes";
controlButton.closest = (selector) => selector.includes("[data-pm-action]") ? controlButton : (selector.includes("pmControls") ? controls : null);
notesCloseButton.closest = (selector) => selector.includes("[data-pm-action]") ? notesCloseButton : (selector.includes("pmNotesPanel") ? notesPanel : null);
helpButton.closest = (selector) => selector.includes("[data-pm-action]") ? helpButton : (selector.includes("pmControls") ? controls : null);
helpCloseButton.closest = (selector) => selector.includes("[data-pm-action]") ? helpCloseButton : (selector.includes("pmHelpPanel") ? helpPanel : null);
const elements = { pmApp: app, pmStage: stage, pmDeck: deck, pmControls: controls, pmPageCount: pageCount, pmProgress: progress, pmNotesPanel: notesPanel, pmNotesContent: notesContent, pmNotesData: notesData, pmHelpPanel: helpPanel, pmRuntimeData: runtimeData };
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
const context = { document, window, history, app, stage, controls, controlButton, notesCloseButton, notesPanel, helpButton, helpCloseButton, helpPanel, notesContent, slideOne, slideTwo, visibleSlideChild, listeners, timerCallbacks };
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
            "if (window.location.hash !== '#slide=01') throw new Error('malformed hash was not normalized');",
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_accepts_raw_and_named_slide_hashes_and_canonicalizes_them(self) -> None:
        for hash_value in ("#02", "#slide=02"):
            with self.subTest(hash_value=hash_value):
                result = self.run_runtime_probe(
                    hash_value,
                    "if (!slideTwo.classList.contains('pm-active')) throw new Error('slide two was not activated');"
                    "if (window.location.hash !== '#slide=02') throw new Error('hash was not canonicalized');",
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

    def test_question_mark_toggles_shortcut_help_and_returns_focus(self) -> None:
        result = self.run_runtime_probe(
            "",
            "const keyEvent = { key: '?', shiftKey: true, altKey: false, ctrlKey: false, metaKey: false, target: stage, preventDefault() {} };"
            "listeners.document.keydown(keyEvent);"
            "if (helpPanel.hidden || document.activeElement !== helpCloseButton) throw new Error('help did not open');"
            "listeners.document.click({ target: helpCloseButton, preventDefault() {} });"
            "if (!helpPanel.hidden || document.activeElement !== helpButton) throw new Error('help did not close cleanly');",
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_missing_notes_uses_localized_runtime_copy(self) -> None:
        result = self.run_runtime_probe(
            "",
            "if (notesContent.textContent !== '本页没有演讲者备注。') throw new Error('localized no-notes copy missing');",
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
            "listeners.stage.pointerdown({ pointerType: 'mouse', clientX: 10, clientY: 10, target: stage });"
            "if (app.classList.contains('pm-controls-hidden')) throw new Error('stage pointer did not reveal controls');",
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_click_on_visible_slide_content_advances_once(self) -> None:
        result = self.run_runtime_probe(
            "",
            "listeners.stage.click({ target: visibleSlideChild });"
            "if (!slideTwo.classList.contains('pm-active')) throw new Error('visible slide click did not advance');",
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_powerpoint_and_remote_keyboard_navigation(self) -> None:
        result = self.run_runtime_probe(
            "",
            "const keyEvent = (key, shiftKey = false) => ({ key, shiftKey, altKey: false, ctrlKey: false, metaKey: false, target: stage, preventDefault() {} });"
            "listeners.document.keydown(keyEvent('PageDown'));"
            "if (!slideTwo.classList.contains('pm-active')) throw new Error('PageDown did not advance');"
            "listeners.document.keydown(keyEvent('p'));"
            "if (!slideOne.classList.contains('pm-active')) throw new Error('P did not go back');"
            "listeners.document.keydown(keyEvent('n'));"
            "if (!slideTwo.classList.contains('pm-active')) throw new Error('N did not advance');"
            "listeners.document.keydown(keyEvent(' ' , true));"
            "if (!slideOne.classList.contains('pm-active')) throw new Error('Shift+Space did not go back');",
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_mouse_wheel_navigates_and_prevents_page_scroll(self) -> None:
        result = self.run_runtime_probe(
            "",
            "let prevented = false;"
            "listeners.stage.wheel({ target: stage, deltaX: 0, deltaY: 120, ctrlKey: false, preventDefault() { prevented = true; } });"
            "if (!prevented) throw new Error('wheel scrolling was not contained');"
            "if (!slideTwo.classList.contains('pm-active')) throw new Error('wheel did not advance');",
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
        (self.images / "captions.vtt").write_text("WEBVTT", encoding="utf-8")
        (self.images / "module.js").write_text("export default 1;", encoding="utf-8")
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

    def test_rewrites_srcdoc_with_local_assets_and_nested_local_iframe(self) -> None:
        interactive = self.project / "interactive"
        interactive.mkdir()
        (interactive / "child.html").write_text(
            '<img src="../images/chart.png">', encoding="utf-8"
        )
        srcdoc = '<img src="../../images/chart.png"><iframe src="../../interactive/child.html"></iframe>'
        packager = OfflineResourcePackager(self.project)

        rewritten = packager.rewrite_html(
            f'<iframe srcdoc="{escape(srcdoc, quote=True)}"></iframe>', self.slide_path
        )

        outer = BeautifulSoup(rewritten, "html.parser").iframe
        srcdoc_html = outer["srcdoc"]
        self.assertIn(self.data_uri("image/png", self.chart), srcdoc_html)
        nested = BeautifulSoup(srcdoc_html, "html.parser").iframe
        child_html = b64decode(nested["src"].split(",", 1)[1]).decode("utf-8")
        self.assertIn(self.data_uri("image/png", self.chart), child_html)
        self.assertNotIn("../../images/", srcdoc_html)

    def test_srcdoc_takes_precedence_and_removes_ignored_src(self) -> None:
        srcdoc = '<img src="../../images/chart.png">'
        packager = OfflineResourcePackager(self.project)

        rewritten = packager.rewrite_html(
            '<iframe src="../../interactive/does-not-need-to-exist.html" '
            f'srcdoc="{escape(srcdoc, quote=True)}"></iframe>',
            self.slide_path,
        )

        iframe = BeautifulSoup(rewritten, "html.parser").iframe
        self.assertNotIn("src", iframe.attrs)
        self.assertIn(self.data_uri("image/png", self.chart), iframe["srcdoc"])

    def test_rejects_remote_runtime_resource_inside_srcdoc(self) -> None:
        packager = OfflineResourcePackager(self.project)
        srcdoc = '<img src="https://example.test/chart.png">'

        with self.assertRaisesRegex(PackagingError, "remote runtime"):
            packager.rewrite_html(
                f'<iframe srcdoc="{escape(srcdoc, quote=True)}"></iframe>', self.slide_path
            )

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

    def test_rejects_resources_without_a_determinate_media_type(self) -> None:
        unknown = self.images / "required-resource.unknown"
        unknown.write_bytes(b"unknown")
        packager = OfflineResourcePackager(self.project)

        with self.assertRaisesRegex(PackagingError, "MIME type"):
            packager.rewrite_html('<img src="../../images/required-resource.unknown">', self.slide_path)

    def test_embeds_extended_runtime_fetching_attributes_and_preserves_svg_fragments(self) -> None:
        packager = OfflineResourcePackager(self.project)
        source = """
        <track src="../../images/captions.vtt">
        <object data="../../images/chart.png"></object>
        <embed src="../../images/chart.png">
        <svg>
          <image href="../../images/chart.png"></image>
          <feImage xlink:href="../../images/chart.png"></feImage>
          <image href="#paint"></image>
          <use href="#symbol"></use>
          <use xlink:href="#symbol-two"></use>
        </svg>
        <link rel="icon" href="../../images/chart.png">
        <link rel="preload" href="../../images/demo.woff2">
        <link rel="modulepreload" href="../../images/module.js">
        <a href="https://example.test/keep">Keep this link</a>
        """

        rewritten = packager.rewrite_html(source, self.slide_path)

        self.assertIn('src="data:text/vtt;base64,', rewritten)
        self.assertGreaterEqual(rewritten.count(self.data_uri("image/png", self.chart)), 5)
        self.assertIn(self.data_uri("font/woff2", self.font), rewritten)
        self.assertIn('href="data:text/javascript;base64,', rewritten)
        self.assertIn('href="#paint"', rewritten)
        self.assertIn('href="#symbol"', rewritten)
        self.assertIn('xlink:href="#symbol-two"', rewritten)
        self.assertIn('href="https://example.test/keep"', rewritten)
        self.assertNotIn("../../images/", rewritten)

    def test_rejects_extended_remote_resources_and_external_svg_use(self) -> None:
        packager = OfflineResourcePackager(self.project)
        for markup in (
            '<track src="https://example.test/captions.vtt">',
            '<object data="https://example.test/object">',
            '<embed src="https://example.test/embed">',
            '<svg><image href="https://example.test/image.png"></image></svg>',
            '<svg><feImage xlink:href="https://example.test/image.png"></feImage></svg>',
            '<link rel="icon" href="https://example.test/icon.png">',
            '<link rel="preload" href="https://example.test/font.woff2">',
            '<link rel="modulepreload" href="https://example.test/module.js">',
            '<svg><use href="../../images/symbols.svg#symbol"></use></svg>',
            '<svg><use xlink:href="https://example.test/symbols.svg#symbol"></use></svg>',
        ):
            with self.subTest(markup=markup):
                with self.assertRaisesRegex(PackagingError, "remote runtime|external SVG <use>"):
                    packager.rewrite_html(markup, self.slide_path)

    def test_final_validation_rejects_extended_unresolved_runtime_references(self) -> None:
        for document in (
            '<track src="local.vtt">',
            '<object data="local.html"></object>',
            '<embed src="local.pdf">',
            '<svg><image href="local.png"></image></svg>',
            '<svg><feImage xlink:href="local.png"></feImage></svg>',
            '<link rel="icon" href="local.png">',
            '<link rel="preload" href="local.woff2">',
            '<link rel="modulepreload" href="local.js">',
            '<svg><use href="local.svg#symbol"></use></svg>',
        ):
            with self.subTest(document=document):
                with self.assertRaises(PackagingError):
                    _validate_offline_document(document)

    def test_final_validation_recursively_rejects_runtime_references_inside_srcdoc(self) -> None:
        for srcdoc in (
            '<img src="local.png">',
            '<img src="https://example.test/chart.png">',
            '<iframe src="nested.html"></iframe>',
        ):
            with self.subTest(srcdoc=srcdoc):
                with self.assertRaises(PackagingError):
                    _validate_offline_document(f'<iframe srcdoc="{escape(srcdoc, quote=True)}"></iframe>')

    def test_final_validation_rejects_remote_dependency_inside_data_iframe(self) -> None:
        iframe_html = '<script src="https://example.test/runtime.js"></script>'
        data_uri = self.data_uri("text/html", iframe_html.encode("utf-8"))

        with self.assertRaisesRegex(
            PackagingError, r"iframe data URI.*https://example\.test/runtime\.js"
        ):
            _validate_offline_document(f'<iframe src="{data_uri}"></iframe>')

    def test_final_validation_rejects_malformed_undecodable_and_non_html_data_iframes(self) -> None:
        invalid_data_uris = (
            "data:text/html;base64,not-base64!",
            "data:text/html;base64,/w==",
            "data:text/html,%ZZ",
            "data:text/plain,%3Cp%3Enot%20html%3C%2Fp%3E",
        )

        for data_uri in invalid_data_uris:
            with self.subTest(data_uri=data_uri):
                with self.assertRaisesRegex(PackagingError, "iframe data URI"):
                    _validate_offline_document(f'<iframe src="{data_uri}"></iframe>')

    def test_final_validation_accepts_nested_base64_and_percent_encoded_data_iframes(self) -> None:
        inner_html = '<img src="data:image/png;base64,AAAA">'
        inner_data_uri = f"data:text/html;charset=utf-8,{quote(inner_html, safe='')}"
        outer_html = f'<iframe src="{inner_data_uri}"></iframe>'
        outer_data_uri = self.data_uri("text/html", outer_html.encode("utf-8"))

        _validate_offline_document(f'<iframe src="{outer_data_uri}"></iframe>')

    def test_final_validation_caps_data_iframe_nesting_depth(self) -> None:
        document = "<p>deepest</p>"
        for _ in range(20):
            data_uri = self.data_uri("text/html", document.encode("utf-8"))
            document = f'<iframe src="{data_uri}"></iframe>'

        with self.assertRaisesRegex(PackagingError, "iframe nesting depth"):
            _validate_offline_document(document)

    def test_final_validation_caps_decoded_data_iframe_size(self) -> None:
        data_uri = self.data_uri("text/html", b"<p>too large</p>")

        with patch("build_single_html._MAX_DECODED_DATA_IFRAME_BYTES", 8):
            with self.assertRaisesRegex(PackagingError, "decoded payload exceeds"):
                _validate_offline_document(f'<iframe src="{data_uri}"></iframe>')

    def test_final_validation_allows_fragment_only_svg_references_and_external_anchors(self) -> None:
        _validate_offline_document(
            '<svg><image href="#paint"></image><feImage xlink:href="#filter"></feImage>'
            '<use href="#symbol"></use><use xlink:href="#symbol-two"></use></svg>'
            '<a href="https://example.test/keep">Keep</a>'
        )


class AtomicWriteTests(ProjectFixture):
    def test_reports_bytes_without_calling_path_stat_after_replacement(self) -> None:
        target = self.project / "exports" / "deck.single.html"
        target.parent.mkdir()
        document = "<html>new</html>"

        with patch.object(Path, "stat", side_effect=AssertionError("stat must not run after replacement")):
            bytes_written = _write_atomically(target, document)

        self.assertEqual(bytes_written, len(document.encode("utf-8")))
        self.assertEqual(target.read_text(encoding="utf-8"), document)

    def test_removes_temp_file_when_the_atomic_write_fails(self) -> None:
        target = self.project / "exports" / "deck.single.html"
        target.parent.mkdir()
        target.write_text("existing", encoding="utf-8")
        temporary_path = target.parent / ".deck.single.html.failure.tmp"
        temporary_path.write_text("partial", encoding="utf-8")

        class FailingTemporaryFile:
            name = str(temporary_path)

            def __enter__(self) -> "FailingTemporaryFile":
                return self

            def __exit__(self, *_args: object) -> bool:
                return False

            def write(self, _document: str) -> int:
                raise OSError("simulated write failure")

        with patch("build_single_html.tempfile.NamedTemporaryFile", return_value=FailingTemporaryFile()):
            with self.assertRaisesRegex(OSError, "simulated write failure"):
                _write_atomically(target, "replacement")

        self.assertEqual(target.read_text(encoding="utf-8"), "existing")
        self.assertFalse(temporary_path.exists())


class BuildSingleHtmlTests(ProjectFixture):
    def setUp(self) -> None:
        super().setUp()
        self.write_manifest(MANIFEST)
        (self.project / "images").mkdir()
        (self.project / "images" / "chart.png").write_bytes(b"\x89PNG\r\n\x1a\nchart")
        (self.project / "images" / "demo.woff2").write_bytes(b"woff2-demo")
        interactive = self.project / "interactive"
        interactive.mkdir()
        (interactive / "widget.css").write_text(
            '.widget { background: url("../images/chart.png"); }', encoding="utf-8"
        )
        (interactive / "widget.js").write_text("window.widgetReady = true;", encoding="utf-8")
        (interactive / "widget.html").write_text(
            '<link rel="stylesheet" href="widget.css"><img src="../images/chart.png">'
            '<script src="widget.js"></script>',
            encoding="utf-8",
        )
        (self.project / "html_output" / "presentation.css").write_text(
            '@font-face { src: url("../images/demo.woff2"); }\n'
            '.hero { background-image: url("../images/chart.png"); }',
            encoding="utf-8",
        )
        (self.project / "html_output" / "slides" / "01_cover.html").write_text(
            '<section class="pm-slide" data-slide-id="01"><img src="../../images/chart.png">'
            '<iframe src="../../interactive/widget.html"></iframe>'
            '<a href="https://example.test/brief">Read more</a></section>',
            encoding="utf-8",
        )
        (self.project / "html_output" / "slides" / "02_overview.html").write_text(
            '<section class="pm-slide" data-slide-id="02">Overview</section>', encoding="utf-8"
        )
        (self.project / "notes" / "total.md").write_text(
            "# 01 Cover\nOpening speaker notes\n---\n# 02 Overview\nClosing speaker notes\n",
            encoding="utf-8",
        )

    def test_builds_a_stable_offline_document_with_hidden_notes(self) -> None:
        result = build_single_html(self.project)
        output = self.project / "exports" / f"{self.project.name}.single.html"
        document = output.read_text(encoding="utf-8")

        self.assertEqual(result["status"], "ok")
        self.assertEqual(Path(result["output_html"]), output.resolve())
        self.assertEqual(result["output_file_url"], output.resolve().as_uri())
        self.assertEqual(result["slides"], 2)
        self.assertGreaterEqual(result["embedded_assets"], 4)
        self.assertGreaterEqual(result["media"]["unique_assets"], 2)
        self.assertEqual(
            result["media"]["reference_count"], result["embedded_assets"]
        )
        self.assertGreater(result["media"]["embedded_payload_bytes"], 0)
        self.assertEqual(result["warnings"], [])
        self.assertIn("Opening speaker notes", document)
        self.assertIn('id="pmNotesPanel"', document)
        self.assertIn("hidden", document)
        self.assertIn('href="https://example.test/brief"', document)
        for unresolved in (
            "../images/",
            "widget.html",
            "widget.css",
            "widget.js",
            "presentation.css",
            str(self.project),
        ):
            self.assertNotIn(unresolved, document)
        self.assertNotIn("https://example.test/brief\" src", document)

    def test_rerun_replaces_the_same_default_target(self) -> None:
        first = build_single_html(self.project)
        first_bytes = Path(first["output_html"]).read_bytes()
        second = build_single_html(self.project)

        self.assertEqual(first["output_html"], second["output_html"])
        self.assertEqual(first_bytes, Path(second["output_html"]).read_bytes())
        self.assertEqual(
            list((self.project / "exports").glob("*.single.html")),
            [self.project / "exports" / f"{self.project.name}.single.html"],
        )

    def test_failed_build_keeps_an_existing_target_byte_identical(self) -> None:
        target = Path(build_single_html(self.project)["output_html"])
        original = target.read_bytes()
        (self.project / "html_output" / "slides" / "02_overview.html").write_text(
            '<section class="pm-slide" data-slide-id="wrong">Broken</section>', encoding="utf-8"
        )

        with self.assertRaisesRegex(PackagingError, "data-slide-id"):
            build_single_html(self.project)

        self.assertEqual(target.read_bytes(), original)
        self.assertEqual(list(target.parent.glob(f".{target.name}.*.tmp")), [])

    def test_missing_notes_key_raises_with_slide_key_and_source(self) -> None:
        manifest = json.loads(json.dumps(MANIFEST))
        manifest["slides"][1]["notes_key"] = "missing-notes"
        self.write_manifest(manifest)

        with self.assertRaises(PackagingError) as caught:
            build_single_html(self.project)

        message = str(caught.exception)
        self.assertIn("slides[1]", message)
        self.assertIn("02", message)
        self.assertIn("missing-notes", message)
        self.assertIn(str(self.project / "notes" / "total.md"), message)
        self.assertIn("omit notes_key", message)

    def test_notes_key_defaults_to_slide_id(self) -> None:
        manifest = json.loads(json.dumps(MANIFEST))
        for slide in manifest["slides"]:
            slide.pop("notes_key", None)
        self.write_manifest(manifest)

        result = check_single_html(self.project)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["mode"], "check")

    def test_check_validates_without_writing_export(self) -> None:
        output = self.project / "exports" / f"{self.project.name}.single.html"

        result = check_single_html(self.project)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["mode"], "check")
        self.assertEqual(result["slides"], 2)
        self.assertGreater(result["estimated_bytes"], 0)
        self.assertFalse(output.exists())

    def test_warns_when_the_generated_document_exceeds_100_mb(self) -> None:
        (self.project / "html_output" / "presentation.css").write_text(
            "/*" + ("x" * (100 * 1024 * 1024 + 1)) + "*/", encoding="utf-8"
        )

        result = build_single_html(self.project)

        self.assertTrue(any("50 MB" in warning for warning in result["warnings"]))
        self.assertTrue(any("100 MB" in warning for warning in result["warnings"]))

    def test_reports_large_gif_without_transcoding_it(self) -> None:
        gif = self.project / "images" / "demo.gif"
        gif.write_bytes(b"GIF89a-demo")
        (self.project / "html_output" / "slides" / "02_overview.html").write_text(
            '<section class="pm-slide" data-slide-id="02">'
            '<img src="../../images/demo.gif"></section>',
            encoding="utf-8",
        )

        with (
            patch("build_single_html._LARGE_ASSET_WARNING_BYTES", 4),
            patch("build_single_html._LARGE_GIF_WARNING_BYTES", 4),
        ):
            result = check_single_html(self.project)

        self.assertTrue(any("Large embedded asset" in item for item in result["warnings"]))
        self.assertTrue(any("do not transcode automatically" in item for item in result["warnings"]))
        gif_entry = next(
            item
            for item in result["media"]["largest_assets"]
            if item["path"] == "images/demo.gif"
        )
        self.assertEqual(gif_entry["references"], 1)

    def test_cli_json_is_one_object_with_clean_success_stderr(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(SCRIPT_DIR / "build_single_html.py"), str(self.project), "--json"],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["slides"], 2)
        self.assertEqual(completed.stderr, "")

    def test_cli_json_check_is_machine_readable_and_does_not_write(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_DIR / "build_single_html.py"),
                str(self.project),
                "--check",
                "--json",
            ],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["mode"], "check")
        self.assertFalse(
            (self.project / "exports" / f"{self.project.name}.single.html").exists()
        )

    def test_cli_rejects_check_with_output_as_json_error(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_DIR / "build_single_html.py"),
                str(self.project),
                "--check",
                "--output",
                str(self.project / "exports" / "x.html"),
                "--json",
            ],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(completed.returncode, 1)
        payload = json.loads(completed.stdout)
        self.assertIn("--check cannot be combined", payload["error"])

    def test_cli_success_reports_human_readable_build_summary(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(SCRIPT_DIR / "build_single_html.py"), str(self.project)],
            check=False,
            capture_output=True,
            text=True,
        )

        output = (self.project / "exports" / f"{self.project.name}.single.html").resolve()
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn(f"Saved: {output}", completed.stdout)
        self.assertIn("Slides: 2", completed.stdout)
        self.assertRegex(completed.stdout, r"Embedded resources: [1-9]\d*")
        self.assertRegex(completed.stdout, r"Output bytes: [1-9]\d*")
        self.assertIn("Warnings: none", completed.stdout)
        self.assertEqual(completed.stderr, "")

    def test_cli_help_includes_three_copyable_examples(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(SCRIPT_DIR / "build_single_html.py"), "--help"],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        for example in (
            "python3 build_single_html.py projects/quarterly-review --check --json",
            "python3 build_single_html.py projects/quarterly-review",
            "python3 build_single_html.py projects/quarterly-review --output exports/review.html",
            "python3 build_single_html.py projects/quarterly-review --json",
        ):
            self.assertIn(example, completed.stdout)
        self.assertEqual(completed.stderr, "")

    def test_cli_invalid_project_reports_an_actionable_error_without_stdout(self) -> None:
        missing_project = self.project / "missing"
        completed = subprocess.run(
            [sys.executable, str(SCRIPT_DIR / "build_single_html.py"), str(missing_project)],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertNotEqual(completed.returncode, 0)
        self.assertEqual(completed.stdout, "")
        self.assertIn("manifest not found", completed.stderr)

    def test_cli_missing_notes_key_reports_slide_key_and_source_without_stdout(self) -> None:
        manifest = json.loads(json.dumps(MANIFEST))
        manifest["slides"][1]["notes_key"] = "missing-notes"
        self.write_manifest(manifest)

        completed = subprocess.run(
            [sys.executable, str(SCRIPT_DIR / "build_single_html.py"), str(self.project)],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertNotEqual(completed.returncode, 0)
        self.assertEqual(completed.stdout, "")
        self.assertIn("slides[1]", completed.stderr)
        self.assertIn("02", completed.stderr)
        self.assertIn("missing-notes", completed.stderr)
        self.assertIn(str(self.project / "notes" / "total.md"), completed.stderr)

    def test_cli_json_failure_is_a_single_machine_readable_error(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(SCRIPT_DIR / "build_single_html.py"), str(self.project / "missing"), "--json"],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertNotEqual(completed.returncode, 0)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["status"], "error")
        self.assertIn("manifest not found", payload["error"])
        self.assertEqual(completed.stderr, "")


if __name__ == "__main__":
    unittest.main()
