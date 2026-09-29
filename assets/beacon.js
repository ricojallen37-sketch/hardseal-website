/*
 * Hardseal first-party page beacon.
 *
 * Sends a single aggregate page-view ping to /api/beacon on hardseal.ai.
 * No cookies. No localStorage. No third-party domains. No personal data.
 * Source is visible at https://hardseal.ai/assets/beacon.js.
 *
 * Loaded only on marketing and legal pages. Never on /verify.html or
 * anything under /proof/ — those pages must remain network-silent except
 * for explicit user actions.
 */
(function () {
  try {
    var path = window.location.pathname || "/";
    var rawRef = "";
    try {
      var params = new URLSearchParams(window.location.search || "");
      rawRef = params.get("ref") || "";
    } catch (e) { /* old browser — skip ref */ }
    var ref = rawRef.replace(/[^A-Za-z0-9_\-]/g, "").slice(0, 64);

    var qs = "p=" + encodeURIComponent(path) + (ref ? "&ref=" + encodeURIComponent(ref) : "");
    var url = "/api/beacon?" + qs;

    var sent = false;
    if (navigator && typeof navigator.sendBeacon === "function") {
      sent = navigator.sendBeacon(url);
    }
    if (!sent) {
      try { new Image().src = url; } catch (e) { /* swallow */ }
    }
  } catch (e) {
    /* Never let the beacon throw into page code. */
  }
})();
