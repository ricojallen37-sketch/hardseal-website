/* ----------------------------------------------------------------------
 * HardSeal Verified — embeddable badge
 * ----------------------------------------------------------------------
 * Drop-in trust mark for any supplier delivery, portal, or page. Zero
 * dependencies. Renders synchronously (<300ms), works cross-origin, and
 * links to the full client-side verifier at https://hardseal.ai/v/?id=<id>.
 *
 *   <a class="hardseal-badge" data-hardseal-id="receipt-001-..."></a>
 *   <script src="https://hardseal.ai/badge.js" async></script>
 *
 * Optional attributes:
 *   data-hardseal-id      receipt id (required) — what /v/ resolves
 *   data-hardseal-state   "ok" (default) | "fail" | "neutral"
 *   data-hardseal-theme   "dark" (default) | "light"
 *   data-hardseal-compact "true" for icon + "Verified" only
 *
 * Public API: window.HardsealBadge.render(el) / .init()
 * -------------------------------------------------------------------- */
(function () {
  "use strict";

  var ORIGIN = "https://hardseal.ai";
  var STYLE_ID = "hardseal-badge-style";
  var DONE = "data-hsb-done";

  function injectStyle() {
    if (document.getElementById(STYLE_ID)) return;
    var css =
      ".hardseal-badge{all:unset;display:inline-flex;align-items:center;gap:8px;" +
      "font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;" +
      "font-size:12px;line-height:1;font-weight:600;letter-spacing:.02em;" +
      "padding:8px 12px;border-radius:6px;cursor:pointer;text-decoration:none;" +
      "border:1px solid #2a2a2a;background:#0c0c0c;color:#f4f4f4;vertical-align:middle;" +
      "transition:border-color .15s ease,background .15s ease;box-sizing:border-box}" +
      ".hardseal-badge:hover{border-color:#3d8b54;background:#0f140f}" +
      ".hardseal-badge[data-hardseal-theme='light']{background:#fff;color:#111;border-color:#e2e2e2}" +
      ".hardseal-badge[data-hardseal-theme='light']:hover{border-color:#22c55e;background:#f6fef9}" +
      ".hardseal-badge .hsb-ico{display:inline-flex;width:16px;height:16px;flex:0 0 16px}" +
      ".hardseal-badge .hsb-ico svg{width:16px;height:16px;display:block}" +
      ".hardseal-badge .hsb-main{font-weight:700;white-space:nowrap}" +
      ".hardseal-badge .hsb-sub{color:#9a9a9a;font-weight:500;white-space:nowrap}" +
      ".hardseal-badge[data-hardseal-theme='light'] .hsb-sub{color:#6a6a6a}" +
      ".hardseal-badge .hsb-sub:before{content:'•';margin-right:8px;color:inherit;opacity:.5}";
    var el = document.createElement("style");
    el.id = STYLE_ID;
    el.textContent = css;
    (document.head || document.documentElement).appendChild(el);
  }

  function icon(state) {
    if (state === "fail") {
      return '<span class="hsb-ico"><svg viewBox="0 0 24 24" fill="none">' +
        '<circle cx="12" cy="12" r="10" fill="#ef4444"/>' +
        '<path d="M8 8l8 8M16 8l-8 8" stroke="#fff" stroke-width="2.2" stroke-linecap="round"/></svg></span>';
    }
    if (state === "neutral") {
      return '<span class="hsb-ico"><svg viewBox="0 0 24 24" fill="none">' +
        '<circle cx="12" cy="12" r="10" fill="#555"/>' +
        '<path d="M12 7v6M12 16.5v.5" stroke="#fff" stroke-width="2.2" stroke-linecap="round"/></svg></span>';
    }
    return '<span class="hsb-ico"><svg viewBox="0 0 24 24" fill="none">' +
      '<circle cx="12" cy="12" r="10" fill="#22c55e"/>' +
      '<path d="M7.5 12.5l3 3 6-6.5" stroke="#fff" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round"/></svg></span>';
  }

  function render(el) {
    if (!el || el.getAttribute(DONE) === "1") return;
    injectStyle();

    var id = el.getAttribute("data-hardseal-id") || el.getAttribute("data-id") || "";
    var state = (el.getAttribute("data-hardseal-state") || "ok").toLowerCase();
    var compact = (el.getAttribute("data-hardseal-compact") || "") === "true";
    var url = ORIGIN + "/v/?id=" + encodeURIComponent(id);

    var main = state === "fail" ? "HardSeal · check failed" : "HardSeal Verified";
    var sub = compact ? "" : (state === "fail" ? "View report" : "View proof");

    var inner = icon(state) +
      '<span class="hsb-main">' + main + "</span>" +
      (sub ? '<span class="hsb-sub">' + sub + "</span>" : "");

    el.innerHTML = inner;
    el.setAttribute("role", "link");

    if (el.tagName === "A") {
      if (id) el.setAttribute("href", url);
      el.setAttribute("target", "_blank");
      el.setAttribute("rel", "noopener noreferrer");
    } else {
      el.style.cursor = "pointer";
      el.addEventListener("click", function () { if (id) window.open(url, "_blank", "noopener"); });
    }
    el.setAttribute("aria-label", main + (id ? " — open verification proof" : ""));
    el.setAttribute(DONE, "1");
  }

  function init(root) {
    var scope = root || document;
    var nodes = scope.querySelectorAll(".hardseal-badge,[data-hardseal-id]");
    Array.prototype.forEach.call(nodes, render);
  }

  window.HardsealBadge = { render: render, init: init };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () { init(); });
  } else {
    init();
  }
})();
