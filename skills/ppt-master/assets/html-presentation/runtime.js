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
  const slides = Array.from(deck.querySelectorAll(".pm-slide"));
  let currentIndex = 0;
  let pointerStart = null;
  let touchStart = null;
  let controlsTimer = null;
  let notes = {};

  try {
    notes = JSON.parse(notesData.textContent || "{}");
  } catch (_error) {
    notes = {};
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
    const hash = `#${encodeURIComponent(active.dataset.slideId || String(currentIndex + 1))}`;
    if (window.location.hash !== hash) {
      history.replaceState(null, "", hash);
    }
  }

  function hashSlideId() {
    const value = window.location.hash.slice(1);
    try {
      return decodeURIComponent(value);
    } catch (_error) {
      return value;
    }
  }

  function renderNotes() {
    const active = slides[currentIndex];
    const entry = active ? notes[active.dataset.slideId] : null;
    const script = entry && entry.script ? entry.script : "No speaker notes for this slide.";
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

  function toggleNotes() {
    const open = notesPanel.hidden;
    notesPanel.hidden = !open;
    notesPanel.setAttribute("aria-hidden", String(!open));
    if (open) notesPanel.querySelector("button").focus();
  }

  function revealControls() {
    app.classList.remove("pm-controls-hidden");
    window.clearTimeout(controlsTimer);
    controlsTimer = window.setTimeout(() => {
      const focused = document.activeElement;
      if (focused && focused.closest && focused.closest("#pmControls, #pmNotesPanel")) {
        revealControls();
        return;
      }
      app.classList.add("pm-controls-hidden");
    }, 2400);
  }

  function restoreHash() {
    const requested = hashSlideId();
    const found = slides.findIndex((slide) => slide.dataset.slideId === requested);
    show(found >= 0 ? found : 0, found < 0);
  }

  document.addEventListener("click", (event) => {
    const action = event.target.closest("[data-pm-action]");
    if (!action) return;
    const handlers = {
      previous: () => go(-1),
      next: () => go(1),
      fullscreen: toggleFullscreen,
      notes: toggleNotes,
    };
    const handler = handlers[action.dataset.pmAction];
    if (handler) {
      event.preventDefault();
      handler();
      revealControls();
    }
  });

  stage.addEventListener("click", (event) => {
    const activeSlide = slides[currentIndex];
    if (!isInteractiveTarget(event.target) && (
      event.target === stage || event.target === deck || event.target === activeSlide
    )) go(1);
  });

  document.addEventListener("keydown", (event) => {
    if (isInteractiveTarget(event.target)) return;
    switch (event.key) {
      case "ArrowLeft":
      case "PageUp":
        event.preventDefault();
        go(-1);
        break;
      case "ArrowRight":
      case "PageDown":
      case " ":
      case "Space":
      case "Spacebar":
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
      case "n":
      case "N":
        event.preventDefault();
        toggleNotes();
        break;
      default:
        return;
    }
    revealControls();
  });

  stage.addEventListener("pointerdown", (event) => {
    revealControls();
    if (event.pointerType !== "touch" && !isInteractiveTarget(event.target)) pointerStart = event.clientX;
  });
  stage.addEventListener("pointerup", (event) => {
    if (pointerStart === null || isInteractiveTarget(event.target)) return;
    const delta = event.clientX - pointerStart;
    pointerStart = null;
    if (Math.abs(delta) > 48) go(delta < 0 ? 1 : -1);
  });
  stage.addEventListener("touchstart", (event) => {
    revealControls();
    if (!isInteractiveTarget(event.target)) touchStart = event.changedTouches[0].clientX;
  }, { passive: true });
  stage.addEventListener("touchend", (event) => {
    if (touchStart === null || isInteractiveTarget(event.target)) return;
    const delta = event.changedTouches[0].clientX - touchStart;
    touchStart = null;
    if (Math.abs(delta) > 48) go(delta < 0 ? 1 : -1);
  }, { passive: true });

  window.addEventListener("hashchange", restoreHash);
  window.addEventListener("pointermove", revealControls, { passive: true });
  document.addEventListener("keydown", revealControls);
  document.addEventListener("pointerdown", revealControls, { passive: true });
  document.addEventListener("focusin", revealControls);
  controls.addEventListener("pointermove", revealControls, { passive: true });
  restoreHash();
  revealControls();
})();
