/* Cadence site — nav, theme, waveform, reveals, copy buttons */

(function () {
  "use strict";

  /* nav hairline on scroll */
  var nav = document.querySelector(".nav");
  if (nav) {
    var onScroll = function () {
      nav.classList.toggle("scrolled", window.scrollY > 8);
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
  }

  /* theme toggle (initial theme is set inline in <head>) */
  var toggle = document.querySelector(".theme-toggle");
  if (toggle) {
    toggle.addEventListener("click", function () {
      var root = document.documentElement;
      var next = root.dataset.theme === "dark" ? "light" : "dark";
      root.dataset.theme = next;
      try {
        localStorage.setItem("cadence-theme", next);
      } catch (e) {}
    });
  }

  /* hero waveform — deterministic pattern so it looks composed, not random */
  var wf = document.querySelector(".waveform");
  if (wf) {
    var n = 56;
    var frag = document.createDocumentFragment();
    for (var i = 0; i < n; i++) {
      var bar = document.createElement("i");
      var t = i / (n - 1);
      var h =
        22 +
        58 * Math.abs(Math.sin(t * Math.PI * 3.1)) * (0.55 + 0.45 * Math.sin(t * Math.PI));
      bar.style.setProperty("--h", h.toFixed(1));
      bar.style.setProperty("--d", ((i % 9) * 0.31).toFixed(2));
      frag.appendChild(bar);
    }
    wf.appendChild(frag);
  }

  /* reveal on scroll */
  var revealed = document.querySelectorAll(".reveal");
  if (revealed.length && "IntersectionObserver" in window) {
    var io = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            entry.target.classList.add("in");
            io.unobserve(entry.target);
          }
        });
      },
      { rootMargin: "0px 0px -8% 0px", threshold: 0.08 }
    );
    revealed.forEach(function (el) {
      io.observe(el);
    });
  } else {
    revealed.forEach(function (el) {
      el.classList.add("in");
    });
  }

  /* copy buttons on code blocks */
  document.querySelectorAll(".code").forEach(function (block) {
    var btn = block.querySelector(".copy-btn");
    var pre = block.querySelector("pre");
    if (!btn || !pre) return;
    btn.addEventListener("click", function () {
      var text = pre.innerText.replace(/^\$ /gm, "");
      navigator.clipboard.writeText(text).then(function () {
        btn.textContent = "Copied";
        btn.classList.add("copied");
        setTimeout(function () {
          btn.textContent = "Copy";
          btn.classList.remove("copied");
        }, 1600);
      });
    });
  });
})();
