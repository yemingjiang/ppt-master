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
  if (!encoded) throw new Error("missing encoded preview-QA configuration");
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
  throw new Error(`unable to launch a supported browser. Tried ${attempts.join(" | ")}`);
}

async function run() {
  const config = parseConfiguration();
  const { browser, label: browserLabel } = await launchBrowser(config.browser || "auto");
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  page.setDefaultTimeout(10000);
  page.setDefaultNavigationTimeout(15000);
  const consoleErrors = [];
  const networkRequests = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  page.on("pageerror", (error) => consoleErrors.push(String(error)));
  page.on("request", (request) => {
    if (/^https?:/i.test(request.url())) networkRequests.push(request.url());
  });

  try {
    const previewUrl = pathToFileURL(config.previewPath).href;
    await page.goto(previewUrl, { waitUntil: "load" });
    const slideCount = await page.locator(".slide-link").count();
    if (!slideCount) throw new Error("preview contains no outline slides");
    const entries = await page.evaluate(() => (
      typeof entries === "undefined"
        ? []
        : entries.map((entry) => ({ key: entry.key, title: entry.title }))
    ));
    if (entries.length !== slideCount) {
      throw new Error(`preview entry count ${entries.length} does not match outline ${slideCount}`);
    }

    const checks = {};
    const activeIndex = async () =>
      page.locator(".slide-link.active").getAttribute("data-index");
    const expectIndex = async (expected, label) => {
      await page.waitForTimeout(100);
      const actual = Number(await activeIndex());
      if (actual !== expected) {
        throw new Error(`${label}: expected index ${expected}, got ${actual}`);
      }
    };
    const waitForViewer = async () => {
      await page.locator("#viewer").contentFrame().locator("svg").waitFor({ state: "attached" });
    };

    await expectIndex(0, "initial slide");
    await waitForViewer();
    checks.initial = true;

    if (slideCount > 1) {
      await page.keyboard.press("ArrowRight");
      await expectIndex(1, "ArrowRight");
      await page.keyboard.press("ArrowLeft");
      await expectIndex(0, "ArrowLeft");
      checks.keyboard = true;

      await waitForViewer();
      await page.waitForTimeout(200);
      const sameOriginFrameAccess = await page.evaluate(() => {
        try {
          return Boolean(document.getElementById("viewer")?.contentDocument);
        } catch (_error) {
          return false;
        }
      });
      if (sameOriginFrameAccess) {
        await page.evaluate(() => bindViewerKeyboardNavigation());
        const viewerHandle = await page.locator("#viewer").elementHandle();
        const viewerFrame = viewerHandle ? await viewerHandle.contentFrame() : null;
        if (!viewerFrame) throw new Error("unable to access preview iframe document");
        await viewerFrame.evaluate(() => {
          document.dispatchEvent(
            new KeyboardEvent("keydown", {
              key: "ArrowRight",
              bubbles: true,
              cancelable: true,
            })
          );
        });
        await expectIndex(1, "iframe ArrowRight");
        checks.iframeKeyboard = true;
      } else {
        checks.iframeKeyboard = "not-applicable-file-origin";
      }
    } else {
      checks.keyboard = true;
      checks.iframeKeyboard = true;
    }

    await page.locator(".slide-link").last().click();
    await expectIndex(slideCount - 1, "last outline click");
    const outlineState = await page.evaluate(() => {
      const outline = document.querySelector(".nav");
      const active = document.querySelector(".slide-link.active");
      if (!outline || !active) return null;
      const outlineRect = outline.getBoundingClientRect();
      const activeRect = active.getBoundingClientRect();
      return {
        scrollable: outline.scrollHeight > outline.clientHeight,
        scrollTop: outline.scrollTop,
        activeVisible:
          activeRect.top >= outlineRect.top - 1
          && activeRect.bottom <= outlineRect.bottom + 1,
        documentScrollY: window.scrollY,
      };
    });
    if (!outlineState) throw new Error("outline state is unavailable");
    if (outlineState.scrollable && outlineState.scrollTop <= 0) {
      throw new Error("outline did not scroll to the active last slide");
    }
    if (!outlineState.activeVisible) throw new Error("active outline item is outside its viewport");
    if (outlineState.documentScrollY !== 0) throw new Error("outline navigation scrolled the document");
    checks.outlineFollow = true;

    const lastKey = entries[entries.length - 1].key;
    await page.goto(`${previewUrl}#slide=${encodeURIComponent(lastKey)}`, { waitUntil: "load" });
    await expectIndex(slideCount - 1, "initial URL hash");
    checks.hash = true;

    const containment = await page.evaluate(() => {
      const shell = document.querySelector(".viewer-shell")?.getBoundingClientRect();
      const stage = document.getElementById("slideStage")?.getBoundingClientRect();
      if (!shell || !stage) return null;
      return {
        left: stage.left >= shell.left - 1,
        right: stage.right <= shell.right + 1,
        top: stage.top >= shell.top - 1,
        bottom: stage.bottom <= shell.bottom + 1,
      };
    });
    if (!containment || Object.values(containment).some((value) => !value)) {
      throw new Error(`slide stage is not fully contained: ${JSON.stringify(containment)}`);
    }
    checks.containment = true;

    const requested = Array.isArray(config.slideKeys) && config.slideKeys.length
      ? config.slideKeys
      : entries.map((entry) => entry.key);
    const knownKeys = new Set(entries.map((entry) => entry.key));
    const unknown = requested.filter((key) => !knownKeys.has(key));
    if (unknown.length) throw new Error(`unknown requested slide keys: ${unknown.join(", ")}`);

    const screenshots = [];
    if (config.screenshotsDir) {
      for (const key of requested) {
        const index = entries.findIndex((entry) => entry.key === key);
        await page.locator(".slide-link").nth(index).click();
        await expectIndex(index, `select slide ${key}`);
        await waitForViewer();
        const outputPath = path.join(config.screenshotsDir, `${key}.png`);
        await page.locator("#viewer").screenshot({ path: outputPath });
        screenshots.push(outputPath);
      }
    }
    checks.screenshots = screenshots.length === (config.screenshotsDir ? requested.length : 0);

    if (networkRequests.length) {
      throw new Error(`offline preview made network requests: ${networkRequests.join(", ")}`);
    }
    if (consoleErrors.length) {
      throw new Error(`preview console errors: ${consoleErrors.join(" | ")}`);
    }
    checks.offline = true;
    checks.console = true;

    await browser.close();
    process.stdout.write(JSON.stringify({
      status: "ok",
      browser: browserLabel,
      preview: config.previewPath,
      slides: slideCount,
      tested_slides: requested,
      checks,
      screenshots,
      network_requests: networkRequests,
      console_errors: consoleErrors,
    }));
  } catch (error) {
    await browser.close();
    throw error;
  }
}

run().catch((error) => fail(String(error.message || error)));
