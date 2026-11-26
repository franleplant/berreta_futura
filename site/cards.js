(() => {
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function attachTilt(card) {
    const hero = card.classList.contains("is-hero");
    const maxTilt = hero ? 14 : 11;
    const state = {
      rx: 0,
      ry: 0,
      mx: 50,
      my: 50,
      hyp: 0,
      tx: 0,
      ty: 0,
      tmx: 50,
      tmy: 50,
      thyp: 0,
      active: false,
      raf: 0,
    };

    function apply() {
      const k = state.active ? 0.16 : 0.1;
      state.rx += (state.tx - state.rx) * k;
      state.ry += (state.ty - state.ry) * k;
      state.mx += (state.tmx - state.mx) * k;
      state.my += (state.tmy - state.my) * k;
      state.hyp += (state.thyp - state.hyp) * k;

      const sx = (-state.ry / maxTilt) * (hero ? 18 : 12);
      const sy = (state.rx / maxTilt) * (hero ? 18 : 12);

      card.style.setProperty("--rx", state.rx.toFixed(2) + "deg");
      card.style.setProperty("--ry", state.ry.toFixed(2) + "deg");
      card.style.setProperty("--mx", state.mx.toFixed(1) + "%");
      card.style.setProperty("--my", state.my.toFixed(1) + "%");
      card.style.setProperty("--hyp", state.hyp.toFixed(3));
      card.style.setProperty("--sx", sx.toFixed(1) + "px");
      card.style.setProperty("--sy", sy.toFixed(1) + "px");

      const done =
        !state.active &&
        Math.abs(state.rx) < 0.05 &&
        Math.abs(state.ry) < 0.05 &&
        state.hyp < 0.005;

      if (done) {
        state.rx = 0;
        state.ry = 0;
        state.hyp = 0;
        card.style.setProperty("--rx", "0deg");
        card.style.setProperty("--ry", "0deg");
        card.style.setProperty("--hyp", "0");
        card.style.setProperty("--sx", "0px");
        card.style.setProperty("--sy", "0px");
        state.raf = 0;
        return;
      }
      state.raf = requestAnimationFrame(apply);
    }

    function kick() {
      if (!state.raf) {
        state.raf = requestAnimationFrame(apply);
      }
    }

    function updateFromPoint(clientX, clientY) {
      const rect = card.getBoundingClientRect();
      if (!rect.width || !rect.height) return;
      const px = Math.min(1, Math.max(0, (clientX - rect.left) / rect.width));
      const py = Math.min(1, Math.max(0, (clientY - rect.top) / rect.height));
      const dx = (px - 0.5) * 2;
      const dy = (py - 0.5) * 2;
      const flipped = card.classList.contains("is-flipped");
      state.tx = -dy * maxTilt;
      state.ty = (flipped ? -dx : dx) * maxTilt;
      state.tmx = (flipped ? 1 - px : px) * 100;
      state.tmy = py * 100;
      state.thyp = Math.min(1, Math.hypot(dx, dy));
      state.active = true;
      card.classList.add("is-tilting");
      kick();
    }

    function reset() {
      state.tx = 0;
      state.ty = 0;
      state.tmx = 50;
      state.tmy = 50;
      state.thyp = 0;
      state.active = false;
      card.classList.remove("is-tilting");
      kick();
    }

    if (!reduced) {
      card.addEventListener("pointermove", (e) => {
        if (e.pointerType === "touch" && e.buttons === 0) return;
        updateFromPoint(e.clientX, e.clientY);
      });
      card.addEventListener("pointerleave", reset);
      card.addEventListener("pointercancel", reset);
    }
  }

  document.querySelectorAll(".mtg-card[data-tilt]").forEach(attachTilt);

  const heroCard = document.querySelector(".mtg-card[data-flippable]");
  const flipBtn = document.querySelector("[data-flip]");
  if (heroCard) {
    let downX = 0;
    let downY = 0;
    let flipTimer = 0;

    function toggleFlip() {
      heroCard.classList.add("is-flipping");
      clearTimeout(flipTimer);
      flipTimer = setTimeout(() => heroCard.classList.remove("is-flipping"), 700);
      const flipped = heroCard.classList.toggle("is-flipped");
      heroCard.setAttribute("aria-pressed", String(flipped));
      if (flipBtn) {
        flipBtn.textContent = flipped
          ? flipBtn.dataset.front || "Show front"
          : flipBtn.dataset.back || "Flip card";
        flipBtn.setAttribute("aria-pressed", String(flipped));
      }
    }

    heroCard.addEventListener("pointerdown", (e) => {
      downX = e.clientX;
      downY = e.clientY;
    });
    heroCard.addEventListener("click", (e) => {
      if (Math.hypot(e.clientX - downX, e.clientY - downY) > 10) return;
      toggleFlip();
    });
    heroCard.addEventListener("keydown", (e) => {
      if (e.key === " " || e.key === "Enter") {
        e.preventDefault();
        toggleFlip();
      }
    });
    if (flipBtn) {
      flipBtn.addEventListener("click", toggleFlip);
    }
  }

  const hand = document.querySelector("[data-hand]");
  if (hand) {
    const allSlots = Array.from(hand.querySelectorAll(".hand-slot"));
    const filters = Array.from(document.querySelectorAll(".card-filter"));
    const tally = document.querySelector(".card-tally");
    let visible = allSlots.slice();
    let activeIdx = -1;

    function fan() {
      const n = visible.length;
      const spreadDeg = Math.min(16, Math.max(0, (n - 1) * 2.8));
      const arcDrop = Math.min(44, Math.max(0, (n - 1) * 7.5));
      visible.forEach((slot, i) => {
        const t = n <= 1 ? 0 : (i / (n - 1)) * 2 - 1;
        const rot = t * spreadDeg;
        const y = t * t * arcDrop;
        let nudge = 0;
        if (activeIdx >= 0 && activeIdx !== i) {
          const dist = i - activeIdx;
          nudge = Math.sign(dist) * (Math.abs(dist) === 1 ? 68 : 30);
        }
        slot.style.setProperty("--hr", rot.toFixed(2) + "deg");
        slot.style.setProperty("--hy", y.toFixed(1) + "px");
        slot.style.setProperty("--hn", nudge + "px");
        slot.style.setProperty("--hz", String(10 + i));
        slot.classList.toggle("is-first", i === 0);
        slot.classList.toggle("is-active", i === activeIdx);
      });
    }

    allSlots.forEach((slot) => {
      const enter = () => {
        const idx = visible.indexOf(slot);
        if (idx >= 0) {
          activeIdx = idx;
          fan();
        }
      };
      const leave = () => {
        if (visible[activeIdx] === slot) {
          activeIdx = -1;
          fan();
        }
      };
      slot.addEventListener("pointerenter", enter);
      slot.addEventListener("pointerleave", leave);
      slot.addEventListener("focusin", enter);
      slot.addEventListener("focusout", leave);
    });

    if (filters.length) {
      const plural =
        tally && tally.textContent.includes("carta")
          ? ["1 carta", "cartas"]
          : ["1 card", "cards"];
      filters.forEach((btn) => {
        btn.addEventListener("click", () => {
          const chosen = btn.dataset.filter || "all";
          filters.forEach((b) => b.setAttribute("aria-pressed", String(b === btn)));
          visible = allSlots.filter((slot) => {
            const show = chosen === "all" || slot.dataset.lab === chosen;
            slot.hidden = !show;
            return show;
          });
          activeIdx = -1;
          if (tally) {
            tally.textContent =
              visible.length === 1 ? plural[0] : `${visible.length} ${plural[1]}`;
          }
          fan();
        });
      });
    }

    fan();
  }
})();
