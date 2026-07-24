#!/usr/bin/env node
"use strict";

const path = require("path");
const { pathToFileURL } = require("url");
const { chromium } = require("playwright");

function fail(message, details = []) {
  process.stdout.write(JSON.stringify({ status: "error", error: message, details }));
  process.exitCode = 1;
}

function parseConfiguration() {
  const encoded = process.argv[2];
  if (!encoded) throw new Error("missing encoded QA configuration");
  return JSON.parse(Buffer.from(encoded, "base64").toString("utf8"));
}

async function launchBrowser(browserName) {
  const attempts = [];
  const candidates = browserName === "auto"
    ? [
        ["chrome", { channel: "chrome" }],
        ["msedge", { channel: "msedge" }],
        ["chromium", {}],
      ]
    : [[browserName, browserName === "chromium" ? {} : { channel: browserName }]];
  for (const [label, options] of candidates) {
    try {
      const browser = await chromium.launch({ headless: true, ...options });
      return { browser, label };
    } catch (error) {
      attempts.push(`${label}: ${String(error.message || error).split("\n")[0]}`);
    }
  }
  throw new Error(
    `unable to launch a supported browser. Tried ${attempts.join(" | ")}`
  );
}

async function run() {
  const config = parseConfiguration();
  const { browser, label: browserLabel } = await launchBrowser(config.browser || "auto");
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  const consoleErrors = [];
  const networkRequests = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  page.on("pageerror", (error) => consoleErrors.push(String(error)));
  page.on("request", (request) => {
    if (/^https?:/i.test(request.url())) networkRequests.push(request.url());
  });

  const checks = {};
  const activeSlideId = async () =>
    page.locator(".pm-slide.pm-active").getAttribute("data-slide-id");
  const expectSlide = async (expected, label) => {
    await page.waitForTimeout(70);
    const actual = await activeSlideId();
    if (actual !== expected) {
      throw new Error(`${label}: expected slide ${expected}, got ${actual}`);
    }
  };
  const slideIdAt = async (index) =>
    page.locator(".pm-slide").nth(index).getAttribute("data-slide-id");
  const blur = () => page.evaluate(() => document.activeElement?.blur());
  const pressFromFirst = async (key, label) => {
    await blur();
    await page.keyboard.press("Home");
    await page.keyboard.press(key);
    await expectSlide(await slideIdAt(1), label);
  };
  const pressFromLast = async (key, label) => {
    await blur();
    await page.keyboard.press("End");
    await page.keyboard.press(key);
    const count = await page.locator(".pm-slide").count();
    await expectSlide(await slideIdAt(count - 2), label);
  };
  const dispatchKey = (key) =>
    page.evaluate((value) => {
      document.dispatchEvent(
        new KeyboardEvent("keydown", { key: value, bubbles: true, cancelable: true })
      );
    }, key);

  try {
    await page.goto(pathToFileURL(config.htmlPath).href, { waitUntil: "load" });
    const slideCount = await page.locator(".pm-slide").count();
    if (slideCount < 2) throw new Error("browser QA requires at least two slides");
    const firstId = await slideIdAt(0);
    const secondId = await slideIdAt(1);
    const penultimateId = await slideIdAt(slideCount - 2);
    await expectSlide(firstId, "initial state");
    checks.initial = true;

    for (const [key, label] of [
      ["ArrowRight", "ArrowRight"],
      ["ArrowDown", "ArrowDown"],
      ["PageDown", "PageDown"],
      ["Space", "Space"],
      ["Enter", "Enter"],
      ["n", "N"],
    ]) {
      await pressFromFirst(key, label);
    }
    await blur();
    await page.keyboard.press("Home");
    await dispatchKey("MediaTrackNext");
    await expectSlide(secondId, "MediaTrackNext");
    checks.keyboardNext = true;
    checks.presentationRemoteNext = true;

    for (const [key, label] of [
      ["ArrowLeft", "ArrowLeft"],
      ["ArrowUp", "ArrowUp"],
      ["PageUp", "PageUp"],
      ["Backspace", "Backspace"],
      ["p", "P"],
      ["Shift+Space", "Shift+Space"],
    ]) {
      await pressFromLast(key, label);
    }
    await blur();
    await page.keyboard.press("End");
    await dispatchKey("MediaTrackPrevious");
    await expectSlide(penultimateId, "MediaTrackPrevious");
    checks.keyboardPrevious = true;
    checks.presentationRemotePrevious = true;

    await blur();
    await page.keyboard.press("End");
    await expectSlide(await slideIdAt(slideCount - 1), "End");
    await page.keyboard.press("Home");
    await expectSlide(firstId, "Home");
    checks.homeEnd = true;

    const stage = page.locator("#pmStage");
    const box = await stage.boundingBox();
    if (!box) throw new Error("presentation stage has no bounding box");
    const centerX = box.x + box.width / 2;
    const centerY = box.y + box.height / 2;
    await page.mouse.click(centerX, centerY);
    await expectSlide(secondId, "visible slide click");
    checks.visibleClick = true;

    await blur();
    await page.keyboard.press("Home");
    await page.mouse.move(centerX, centerY);
    await page.mouse.wheel(0, 120);
    await expectSlide(secondId, "wheel next");
    await page.waitForTimeout(500);
    await page.mouse.wheel(0, -120);
    await expectSlide(firstId, "wheel previous");
    checks.wheel = true;

    await page.mouse.move(box.x + box.width * 0.8, centerY);
    await page.mouse.down();
    await page.mouse.move(box.x + box.width * 0.2, centerY, { steps: 5 });
    await page.mouse.up();
    await expectSlide(secondId, "mouse drag exactly once");
    checks.mouseDrag = true;

    await blur();
    await page.keyboard.press("Home");
    await page.evaluate(() => {
      const stageElement = document.getElementById("pmStage");
      const fire = (type, x) => {
        const event = new Event(type, { bubbles: true, cancelable: true });
        Object.defineProperty(event, "changedTouches", {
          value: [{ clientX: x, clientY: 300 }],
        });
        stageElement.dispatchEvent(event);
      };
      fire("touchstart", 900);
      fire("touchend", 100);
    });
    await expectSlide(secondId, "touch swipe exactly once");
    checks.touchSwipe = true;

    await blur();
    await page.keyboard.press("Home");
    await page.locator('[data-pm-action="next"]').click();
    await expectSlide(secondId, "next control");
    await page.locator('[data-pm-action="previous"]').click();
    await expectSlide(firstId, "previous control");
    checks.controls = true;

    await blur();
    await page.keyboard.press("s");
    await page.waitForTimeout(80);
    const notesOpen = await page.locator("#pmNotesPanel").evaluate(
      (element) => !element.hidden && element.getAttribute("aria-hidden") === "false"
    );
    if (!notesOpen) throw new Error("S did not open speaker notes");
    await page.locator('#pmNotesPanel [data-pm-action="notes"]').click();
    checks.notes = true;

    await blur();
    await dispatchKey("?");
    await page.waitForTimeout(80);
    const helpOpen = await page.locator("#pmHelpPanel").evaluate(
      (element) => !element.hidden && element.getAttribute("aria-hidden") === "false"
    );
    if (!helpOpen) throw new Error("? did not open shortcut help");
    await page.locator('#pmHelpPanel [data-pm-action="help"]').click();
    checks.shortcutHelp = true;

    await blur();
    const ctrlFAllowed = await page.evaluate(() =>
      document.dispatchEvent(
        new KeyboardEvent("keydown", {
          key: "f",
          ctrlKey: true,
          bubbles: true,
          cancelable: true,
        })
      )
    );
    if (!ctrlFAllowed) throw new Error("Ctrl/Cmd modified browser shortcuts were intercepted");
    checks.modifiedShortcutsPreserved = true;

    const presentationUrl = pathToFileURL(config.htmlPath).href;
    await page.goto(`${presentationUrl}#${encodeURIComponent(secondId)}`, {
      waitUntil: "load",
    });
    await expectSlide(secondId, "raw URL hash");
    if ((await page.evaluate(() => window.location.hash)) !== `#slide=${encodeURIComponent(secondId)}`) {
      throw new Error("raw URL hash was not canonicalized");
    }
    checks.rawHash = true;

    await page.goto(`${presentationUrl}#slide=${encodeURIComponent(secondId)}`, {
      waitUntil: "load",
    });
    await expectSlide(secondId, "named URL hash");
    checks.namedHash = true;
    checks.hash = true;

    const autoplayVideos = page.locator(".pm-slide video[autoplay]");
    const mediaCount = await autoplayVideos.count();
    let testedMedia = 0;
    for (let mediaIndex = 0; mediaIndex < mediaCount; mediaIndex += 1) {
      const descriptor = await autoplayVideos.nth(mediaIndex).evaluate((element) => {
        const slide = element.closest(".pm-slide");
        const videos = slide ? Array.from(slide.querySelectorAll("video[autoplay]")) : [];
        return {
          slideId: slide?.dataset.slideId || "",
          indexInSlide: videos.indexOf(element),
          placementId: element.dataset.pmPlacementId || "",
        };
      });
      if (!descriptor.slideId || descriptor.indexInSlide < 0) {
        throw new Error(`autoplay video ${mediaIndex + 1} is not inside a slide`);
      }
      await page.goto(
        `${presentationUrl}#slide=${encodeURIComponent(descriptor.slideId)}`,
        { waitUntil: "load" }
      );
      await expectSlide(descriptor.slideId, `autoplay media ${mediaIndex + 1} slide`);
      const activeVideo = descriptor.placementId
        ? page.locator(
          `.pm-slide.pm-active video[autoplay][data-pm-placement-id="${descriptor.placementId}"]`
        )
        : page.locator(".pm-slide.pm-active video[autoplay]").nth(descriptor.indexInSlide);
      const stableVideo = autoplayVideos.nth(mediaIndex);
      if (await activeVideo.count() !== 1) {
        throw new Error(`unable to resolve autoplay video ${mediaIndex + 1} on slide ${descriptor.slideId}`);
      }
      const mediaContract = await activeVideo.evaluate((video) => ({
        autoplay: video.autoplay,
        muted: video.muted,
        loop: video.loop,
        playsInline: video.playsInline,
      }));
      if (
        !mediaContract.autoplay
        || !mediaContract.muted
        || !mediaContract.loop
        || !mediaContract.playsInline
      ) {
        throw new Error(
          `autoplay video ${mediaIndex + 1} on slide ${descriptor.slideId} `
          + "is missing muted/loop/playsinline"
        );
      }
      await page.waitForFunction(
        ({ slideId, placementId, indexInSlide }) => {
          const slide = Array.from(document.querySelectorAll(".pm-slide"))
            .find((candidate) => candidate.dataset.slideId === slideId);
          if (!slide) return false;
          const video = placementId
            ? slide.querySelector(`video[data-pm-placement-id="${placementId}"]`)
            : slide.querySelectorAll("video[autoplay]")[indexInSlide];
          return video && video.readyState >= 2 && !video.paused;
        },
        descriptor
      );
      const initialTime = await activeVideo.evaluate((video) => video.currentTime);
      await page.waitForFunction(
        ({ descriptor, before }) => {
          const slide = Array.from(document.querySelectorAll(".pm-slide"))
            .find((candidate) => candidate.dataset.slideId === descriptor.slideId);
          if (!slide) return false;
          const video = descriptor.placementId
            ? slide.querySelector(`video[data-pm-placement-id="${descriptor.placementId}"]`)
            : slide.querySelectorAll("video[autoplay]")[descriptor.indexInSlide];
          return video && Math.abs(video.currentTime - before) > 0.05;
        },
        { descriptor, before: initialTime }
      );

      const currentSlideIndex = await page.locator(".pm-slide").evaluateAll(
        (slides, slideId) => slides.findIndex((slide) => slide.dataset.slideId === slideId),
        descriptor.slideId
      );
      const awayKey = currentSlideIndex < slideCount - 1 ? "ArrowRight" : "ArrowLeft";
      const returnKey = awayKey === "ArrowRight" ? "ArrowLeft" : "ArrowRight";
      await blur();
      await page.keyboard.press(awayKey);
      await page.waitForTimeout(100);
      // The active-only locator intentionally stops matching after navigation.
      // Keep a document-stable locator for the inactive-state assertion.
      const pausedWhileInactive = await stableVideo.evaluate((video) => video.paused);
      if (!pausedWhileInactive) {
        throw new Error(
          `autoplay video ${mediaIndex + 1} on slide ${descriptor.slideId} `
          + "did not pause when the slide became inactive"
        );
      }
      await page.keyboard.press(returnKey);
      await expectSlide(descriptor.slideId, `return to media ${mediaIndex + 1}`);
      await page.waitForFunction(
        ({ slideId, placementId, indexInSlide }) => {
          const slide = Array.from(document.querySelectorAll(".pm-slide"))
            .find((candidate) => candidate.dataset.slideId === slideId);
          if (!slide) return false;
          const video = placementId
            ? slide.querySelector(`video[data-pm-placement-id="${placementId}"]`)
            : slide.querySelectorAll("video[autoplay]")[indexInSlide];
          return video && !video.paused;
        },
        descriptor
      );
      testedMedia += 1;
    }
    const largeEmbeddedGifs = await page.evaluate(() => {
      const references = [];
      document.querySelectorAll("img[src], image").forEach((element) => {
        const value = element.getAttribute("src")
          || element.getAttribute("href")
          || element.getAttribute("xlink:href")
          || "";
        if (/^data:image\/gif;base64,/i.test(value) && value.length > 8 * 1024 * 1024 * 4 / 3) {
          references.push(value.slice(0, 48));
        }
      });
      return references;
    });
    if (largeEmbeddedGifs.length) {
      throw new Error(`final presentation still contains ${largeEmbeddedGifs.length} large embedded GIF(s)`);
    }
    checks.mediaCount = mediaCount;
    checks.testedMedia = testedMedia;
    checks.noLargeEmbeddedGifs = true;
    checks.mediaPlayback = true;

    await blur();
    await page.keyboard.press("f");
    await page.waitForTimeout(100);
    if (!(await page.evaluate(() => Boolean(document.fullscreenElement)))) {
      throw new Error("F did not enter fullscreen");
    }
    await page.evaluate(async () => {
      if (document.fullscreenElement && document.exitFullscreen) {
        await document.exitFullscreen();
      }
    });
    checks.fullscreen = true;

    const screenshotPaths = [];
    if (config.screenshotsDir) {
      await page.goto(pathToFileURL(config.htmlPath).href, { waitUntil: "load" });
      await page.evaluate(() => {
        const notesPanel = document.getElementById("pmNotesPanel");
        if (notesPanel) {
          notesPanel.hidden = true;
          notesPanel.setAttribute("aria-hidden", "true");
        }
        const helpPanel = document.getElementById("pmHelpPanel");
        if (helpPanel) {
          helpPanel.hidden = true;
          helpPanel.setAttribute("aria-hidden", "true");
        }
        document.activeElement?.blur();
      });
      await page.keyboard.press("Home");
      for (let index = 0; index < slideCount; index += 1) {
        const outputPath = path.join(
          config.screenshotsDir,
          `${String(index + 1).padStart(2, "0")}.png`
        );
        await page.locator("#pmStage").screenshot({ path: outputPath });
        screenshotPaths.push(outputPath);
        if (index < slideCount - 1) {
          await page.keyboard.press("ArrowRight");
          await page.waitForTimeout(100);
        }
      }
      checks.cleanScreenshots = screenshotPaths.length === slideCount;
    }

    if (networkRequests.length) {
      throw new Error(`offline presentation made network requests: ${networkRequests.join(", ")}`);
    }
    if (consoleErrors.length) {
      throw new Error(`browser console errors: ${consoleErrors.join(" | ")}`);
    }
    checks.offline = true;
    checks.console = true;

    await browser.close();
    process.stdout.write(
      JSON.stringify({
        status: "ok",
        browser: browserLabel,
        html: config.htmlPath,
        slides: slideCount,
        checks,
        screenshots: screenshotPaths,
        network_requests: networkRequests,
        console_errors: consoleErrors,
      })
    );
  } catch (error) {
    await browser.close();
    throw error;
  }
}

run().catch((error) => fail(String(error.message || error)));
