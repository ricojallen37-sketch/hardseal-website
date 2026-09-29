/*
 * Hardseal /api/beacon — Cloudflare Worker
 *
 * Purpose: aggregate, first-party page-view counter for hardseal.ai
 * marketing and funnel-hop pages. Counts only — no cookies, no IP
 * storage, no User-Agent storage, no session reconstruction, no PII.
 *
 * Hard rules baked into the code:
 *   1. Only writes (day, path, ref, country, count) to D1.
 *   2. Path is allowlisted — unknown paths bucket to '/_other'.
 *   3. Ref is regex-clamped to [A-Za-z0-9_-]{0,64}.
 *   4. Country is the two-letter Cloudflare-provided code (no city).
 *   5. Day is the UTC calendar date (no timestamp; no per-visit resolution).
 *   6. Returns 204 No Content. Never sets a Set-Cookie header.
 *
 * Source visible at https://github.com/ricojallen37-sketch/hardseal-website/blob/main/worker/src/index.js
 */

const ALLOWED_PATHS = new Set([
  "/",
  "/index.html",
  "/edge.html",
  "/pilot.html",
  "/resources.html",
  "/trophy-case.html",
  "/privacy.html",
  "/terms.html",
  "/dpa.html",
  "/404.html",
  "/p/ir.html",
]);

const PATH_SHAPE = /^\/[A-Za-z0-9_\-./]{0,127}$/;
const REF_SHAPE = /[^A-Za-z0-9_\-]/g;

function normalizePath(raw) {
  let p = (raw || "").slice(0, 128);
  if (!PATH_SHAPE.test(p)) return "/_other";
  if (!ALLOWED_PATHS.has(p)) return "/_other";
  return p;
}

function normalizeRef(raw) {
  return (raw || "").replace(REF_SHAPE, "").slice(0, 64);
}

function normalizeCountry(cf) {
  if (!cf || typeof cf.country !== "string") return "";
  const c = cf.country.toUpperCase();
  return /^[A-Z]{2}$/.test(c) ? c : "";
}

function utcDay() {
  return new Date().toISOString().slice(0, 10);
}

const noStoreHeaders = {
  "Cache-Control": "no-store, must-revalidate",
  "X-Content-Type-Options": "nosniff",
};

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    if (url.pathname !== "/api/beacon") {
      return new Response("Not Found", { status: 404, headers: noStoreHeaders });
    }
    if (request.method !== "GET" && request.method !== "POST") {
      return new Response("Method Not Allowed", { status: 405, headers: noStoreHeaders });
    }

    const params = url.searchParams;
    const path = normalizePath(params.get("p"));
    const ref = normalizeRef(params.get("ref"));
    const country = normalizeCountry(request.cf);
    const day = utcDay();

    if (env && env.DB) {
      try {
        await env.DB.prepare(
          "INSERT INTO beacons (day, path, ref, country, count) VALUES (?, ?, ?, ?, 1) " +
          "ON CONFLICT(day, path, ref, country) DO UPDATE SET count = count + 1"
        ).bind(day, path, ref, country).run();
      } catch (e) {
        // Swallow — beacons are fire-and-forget. Never surface DB errors.
      }
    }

    return new Response(null, { status: 204, headers: noStoreHeaders });
  },
};
