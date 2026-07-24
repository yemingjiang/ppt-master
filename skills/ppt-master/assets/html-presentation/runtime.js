(() => {
  "use strict";

  const app = document.getElementById("pmApp");
  const stage = document.getElementById("pmStage");
  const deck = document.getElementById("pmDeck");
  const controls = document.getElementById("pmControls");
  const pageCount = document.getElementById("pmPageCount");
  const progress = document.getElementById("pmProgress");
  const notesPanel = document.getElementById("pmNotesPanel");
  const notesContent = document.getElementById("pmNotesContent");
  const notesData = document.getElementById("pmNotesData");
  const helpPanel = document.getElementById("pmHelpPanel");
  const runtimeData = document.getElementById("pmRuntimeData");
  const slides = Array.from(deck.querySelectorAll(".pm-slide"));
  let currentIndex = 0;
  let pointerStart = null;
  let touchStart = null;
  let suppressClickUntil = 0;
  let wheelAccumulator = 0;
  let wheelResetTimer = null;
  let lastWheelNavigationAt = 0;
  let controlsTimer = null;
  let notes = {};
  let runtimeText = {};

  try {
    notes = JSON.parse(notesData.textContent || "{}");
  } catch (_error) {
    notes = {};
  }
  try {
    runtimeText = JSON.parse(runtimeData.textContent || "{}");
  } catch (_error) {
    runtimeText = {};
  }

  function isInteractiveTarget(target) {
    return Boolean(
      target && target.closest && target.closest(
        "a, button, input, select, textarea, label, summary, video, audio, iframe, [contenteditable], [data-pm-interactive]"
      )
    );
  }

  function pauseInactiveMedia() {
    slides.forEach((slide, slideIndex) => {
      slide.querySelectorAll("video, audio").forEach((media) => {
        if (slideIndex !== currentIndex) {
          media.pause();
        } else if (media.autoplay) {
          const play = media.play();
          if (play && typeof play.catch === "function") play.catch(() => {});
        }
      });
    });
  }

  function updateHash() {
    const active = slides[currentIndex];
    if (!active) return;
    const hash = `#slide=${encodeURIComponent(active.dataset.slideId || String(currentIndex + 1))}`;
    if (window.location.hash !== hash) {
      history.replaceState(null, "", hash);
    }
  }

  function hashSlideId() {
    const rawValue = window.location.hash.slice(1);
    const value = rawValue.startsWith("slide=") ? rawValue.slice(6) : rawValue;
    try {
      return decodeURIComponent(value);
    } catch (_error) {
      return value;
    }
  }

  function renderNotes() {
    const active = slides[currentIndex];
    const entry = active ? notes[active.dataset.slideId] : null;
    const script = entry && entry.script ? entry.script : (
      runtimeText.noNotes || "No speaker notes for this slide."
    );
    notesContent.textContent = script;
  }

  function show(index, updateLocation = true) {
    if (!slides.length) return;
    currentIndex = Math.max(0, Math.min(index, slides.length - 1));
    slides.forEach((slide, slideIndex) => {
      const active = slideIndex === currentIndex;
      slide.classList.toggle("pm-active", active);
      slide.setAttribute("aria-hidden", String(!active));
    });
    pageCount.textContent = `${currentIndex + 1} / ${slides.length}`;
    progress.style.width = `${((currentIndex + 1) / slides.length) * 100}%`;
    renderNotes();
    pauseInactiveMedia();
    if (updateLocation) updateHash();
  }

  function go(delta) {
    show(currentIndex + delta);
  }

  function toggleFullscreen() {
    if (!document.fullscreenElement) {
      const request = app.requestFullscreen || app.webkitRequestFullscreen;
      if (request) {
        const result = request.call(app);
        if (result && typeof result.catch === "function") result.catch(() => {});
      }
    } else {
      const exit = document.exitFullscreen || document.webkitExitFullscreen;
      if (exit) {
        const result = exit.call(document);
        if (result && typeof result.catch === "function") result.catch(() => {});
      }
    }
  }

  function togglePanel(panel, actionName) {
    const open = panel.hidden;
    [notesPanel, helpPanel].forEach((candidate) => {
      if (candidate !== panel) {
        candidate.hidden = true;
        candidate.setAttribute("aria-hidden", "true");
      }
    });
    panel.hidden = !open;
    panel.setAttribute("aria-hidden", String(!open));
    if (open) {
      panel.querySelector("button").focus();
      return;
    }
    const focused = document.activeElement;
    if (focused && focused.closest && focused.closest(`#${panel.id}`)) {
      const trigger = controls.querySelector(`[data-pm-action="${actionName}"]`);
      if (trigger) trigger.focus();
    }
  }

  function toggleNotes() {
    togglePanel(notesPanel, "notes");
  }

  function toggleHelp() {
    togglePanel(helpPanel, "help");
  }

  function revealControls() {
    app.classList.remove("pm-controls-hidden");
    window.clearTimeout(controlsTimer);
    controlsTimer = window.setTimeout(() => {
      const focused = document.activeElement;
      if (focused && focused.closest && focused.closest("#pmControls, #pmNotesPanel, #pmHelpPanel")) {
        revealControls();
        return;
      }
      app.classList.add("pm-controls-hidden");
    }, 2400);
  }

  function restoreHash() {
    const requested = hashSlideId();
    const found = slides.findIndex((slide) => slide.dataset.slideId === requested);
    show(found >= 0 ? found : 0);
  }

  document.addEventListener("click", (event) => {
    const action = event.target.closest("[data-pm-action]");
    if (!action) return;
    const handlers = {
      previous: () => go(-1),
      next: () => go(1),
      fullscreen: toggleFullscreen,
      notes: toggleNotes,
      help: toggleHelp,
    };
    const handler = handlers[action.dataset.pmAction];
    if (handler) {
      event.preventDefault();
      handler();
      revealControls();
    }
  });

  stage.addEventListener("click", (event) => {
    if (isInteractiveTarget(event.target) || Date.now() < suppressClickUntil) return;
    go(1);
  });

  document.addEventListener("keydown", (event) => {
    if (isInteractiveTarget(event.target) || event.altKey || event.ctrlKey || event.metaKey) return;
    const isSpace = event.key === " " || event.key === "Space" || event.key === "Spacebar";
    if (isSpace && event.shiftKey) {
      event.preventDefault();
      go(-1);
      revealControls();
      return;
    }
    switch (event.key) {
      case "ArrowLeft":
      case "ArrowUp":
      case "PageUp":
      case "Backspace":
      case "p":
      case "P":
      case "MediaTrackPrevious":
        event.preventDefault();
        go(-1);
        break;
      case "ArrowRight":
      case "ArrowDown":
      case "PageDown":
      case " ":
      case "Space":
      case "Spacebar":
      case "Enter":
      case "n":
      case "N":
      case "MediaTrackNext":
        event.preventDefault();
        go(1);
        break;
      case "Home":
        event.preventDefault();
        show(0);
        break;
      case "End":
        event.preventDefault();
        show(slides.length - 1);
        break;
      case "f":
      case "F":
        event.preventDefault();
        toggleFullscreen();
        break;
      case "s":
      case "S":
        event.preventDefault();
        toggleNotes();
        break;
      case "?":
        event.preventDefault();
        toggleHelp();
        break;
      default:
        return;
    }
    revealControls();
  });

  stage.addEventListener("pointerdown", (event) => {
    revealControls();
    if (event.pointerType !== "touch" && !isInteractiveTarget(event.target)) {
      pointerStart = { x: event.clientX, y: event.clientY };
    }
  });
  stage.addEventListener("pointerup", (event) => {
    if (pointerStart === null || isInteractiveTarget(event.target)) return;
    const deltaX = event.clientX - pointerStart.x;
    const deltaY = event.clientY - pointerStart.y;
    pointerStart = null;
    if (Math.abs(deltaX) > 48 && Math.abs(deltaX) > Math.abs(deltaY) * 1.2) {
      suppressClickUntil = Date.now() + 350;
      go(deltaX < 0 ? 1 : -1);
    }
  });
  stage.addEventListener("pointercancel", () => {
    pointerStart = null;
  });
  stage.addEventListener("touchstart", (event) => {
    revealControls();
    if (!isInteractiveTarget(event.target)) {
      touchStart = {
        x: event.changedTouches[0].clientX,
        y: event.changedTouches[0].clientY,
      };
    }
  }, { passive: true });
  stage.addEventListener("touchend", (event) => {
    if (touchStart === null || isInteractiveTarget(event.target)) return;
    const deltaX = event.changedTouches[0].clientX - touchStart.x;
    const deltaY = event.changedTouches[0].clientY - touchStart.y;
    touchStart = null;
    if (Math.abs(deltaX) > 48 && Math.abs(deltaX) > Math.abs(deltaY) * 1.2) {
      suppressClickUntil = Date.now() + 350;
      go(deltaX < 0 ? 1 : -1);
    }
  }, { passive: true });
  stage.addEventListener("touchcancel", () => {
    touchStart = null;
  }, { passive: true });
  stage.addEventListener("wheel", (event) => {
    revealControls();
    if (event.ctrlKey || isInteractiveTarget(event.target)) return;
    const delta = Math.abs(event.deltaY) >= Math.abs(event.deltaX) ? event.deltaY : event.deltaX;
    if (!delta) return;
    event.preventDefault();
    wheelAccumulator += delta;
    window.clearTimeout(wheelResetTimer);
    wheelResetTimer = window.setTimeout(() => {
      wheelAccumulator = 0;
    }, 180);
    if (Math.abs(wheelAccumulator) < 60) return;
    const now = Date.now();
    if (now - lastWheelNavigationAt < 450) {
      wheelAccumulator = 0;
      return;
    }
    go(wheelAccumulator > 0 ? 1 : -1);
    lastWheelNavigationAt = now;
    wheelAccumulator = 0;
  }, { passive: false });

  window.addEventListener("hashchange", restoreHash);
  window.addEventListener("pointermove", revealControls, { passive: true });
  document.addEventListener("pointerdown", revealControls, { passive: true });
  document.addEventListener("focusin", revealControls);
  controls.addEventListener("pointermove", revealControls, { passive: true });
  restoreHash();
  revealControls();
})();
