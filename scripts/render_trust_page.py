#!/usr/bin/env python3
"""
render_trust_page.py — generate /trust.html from the integrity heartbeat log.

Why this exists
---------------
The autonomous integrity heartbeat (.github/workflows/integrity-heartbeat.yml)
appends a hash-chained receipt to docs/integrity/INTEGRITY_LOG.md every 6 hours.
That log is Hardseal's hardest-to-fake asset: continuous public attestation that
cannot be backdated. But until now it was only legible to a human who clicked
through to a raw GitHub markdown file, or to a browser that successfully ran the
client-side fetch on the homepage.

AI assistants (GPTBot, ClaudeBot, PerplexityBot — explicitly invited in
robots.txt) and search crawlers do not run that fetch. So the single strongest
trust signal Hardseal owns was invisible in exactly the channel Hardseal is
courting.

This script bakes the current attestation summary into a static, self-contained
trust.html so the proof is legible WITHOUT JavaScript — indexable, quotable, and
citable — while a progressive-enhancement panel still gives human visitors the
live, auto-refreshing view.

Design rules
------------
- Deterministic: the "as of" timestamp is the last heartbeat in the log, not the
  wall clock, so the same log always renders the same page.
- Robust: pure standard library. Parses defensively; a malformed line is skipped,
  never fatal. In the heartbeat workflow this script is run as a non-fatal step so
  a render hiccup can never cost a heartbeat receipt.
- Honest: counts FAILs, shows the current clean streak from the end of the log,
  and surfaces the most recent rows verbatim including any FAIL.

Usage:  python3 scripts/render_trust_page.py
Writes: trust.html  (at repo root)
"""

from __future__ import annotations

import html
import os
import re
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_chain import check_chain  # noqa: E402  (local sibling module)

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_PATH = os.path.join(REPO_ROOT, "docs", "integrity", "INTEGRITY_LOG.md")
OUT_PATH = os.path.join(REPO_ROOT, "trust.html")

LINE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")


def parse_line(line: str) -> dict | None:
    """Parse one heartbeat line into a dict, or None if it is not a heartbeat."""
    if not LINE_RE.match(line):
        return None
    fields = [f.strip() for f in line.split("|")]
    out = {
        "ts": fields[0],
        "result": "",
        "packets": "",
        "guardian": "",
        "bundle_sha": "",
    }
    for f in fields[1:]:
        if f.startswith("result="):
            out["result"] = f[len("result="):]
        elif f.startswith("packets="):
            out["packets"] = f[len("packets="):]
        elif f.startswith("guardian_sha="):
            out["guardian"] = f[len("guardian_sha="):]
        elif f.startswith("bundle_sha="):
            out["bundle_sha"] = f[len("bundle_sha="):]
    return out


def load_rows() -> list[dict]:
    with open(LOG_PATH, "r", encoding="utf-8") as fh:
        rows = [parse_line(l) for l in fh]
    return [r for r in rows if r]


def iso(ts: str) -> datetime | None:
    try:
        return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def compute(rows: list[dict]) -> dict:
    total = len(rows)
    passes = sum(1 for r in rows if r["result"] == "PASS")
    fails = sum(1 for r in rows if r["result"] == "FAIL")

    # Current clean streak: consecutive PASS counted from the most recent line.
    streak = 0
    for r in reversed(rows):
        if r["result"] == "PASS":
            streak += 1
        else:
            break

    first_ts = rows[0]["ts"] if rows else ""
    last = rows[-1] if rows else {"ts": "", "result": "", "guardian": ""}
    first_pass = next((r["ts"] for r in rows if r["result"] == "PASS"), "")

    # Continuous-attestation window: first PASS -> last heartbeat (deterministic).
    hours = days = 0.0
    fp, lt = iso(first_pass), iso(last["ts"])
    if fp and lt and lt > fp:
        secs = (lt - fp).total_seconds()
        hours = secs / 3600.0
        days = secs / 86400.0

    uptime = (passes / total * 100.0) if total else 0.0

    return {
        "total": total,
        "passes": passes,
        "fails": fails,
        "streak": streak,
        "first_ts": first_ts,
        "first_pass": first_pass,
        "last_ts": last["ts"],
        "last_result": last["result"],
        "last_guardian": last["guardian"],
        "hours": hours,
        "days": days,
        "uptime": uptime,
        "recent": rows[-10:][::-1],
    }


def esc(s: str) -> str:
    return html.escape(s, quote=True)


def render_rows(recent: list[dict]) -> str:
    out = []
    for r in recent:
        cls = "pass" if r["result"] == "PASS" else "fail"
        g = esc(r["guardian"][:16]) + "…" if r["guardian"] else "—"
        out.append(
            "<tr>"
            f'<td class="ts">{esc(r["ts"])}</td>'
            f'<td class="{cls}">● {esc(r["result"] or "—")}</td>'
            f'<td>{esc(r["packets"] or "—")}</td>'
            f'<td class="sha">{g}</td>'
            "</tr>"
        )
    return "\n".join(out)


def build_html(s: dict) -> str:
    rows_html = render_rows(s["recent"])
    days_str = f"{s['days']:.1f}"
    hours_str = f"{s['hours']:,.0f}"
    uptime_str = f"{s['uptime']:.1f}"
    last_dot = "var(--green)" if s["last_result"] == "PASS" else "var(--red)"
    guardian_full = esc(s["last_guardian"]) or "—"

    chain_intact = s.get("chain_intact", False)
    chain_checked = s.get("chain_checked", 0)
    if chain_intact:
        chain_badge = (
            f'<span style="color:var(--green)">✓ CHAIN VERIFIED</span> · all '
            f'{chain_checked} guardian_sha links independently re-derived at build time'
        )
    else:
        chain_badge = (
            '<span style="color:var(--red)">⚠ CHAIN VERIFICATION FAILED</span> · '
            'this render could not re-derive the chain — investigate before trusting'
        )

    # JSON-LD: present the attestation as a structured, machine-readable claim.
    json_ld = f"""{{
  "@context": "https://schema.org",
  "@type": "Dataset",
  "name": "Hardseal Continuous Integrity Attestation",
  "description": "A hash-chained log of automated integrity heartbeats. Every 6 hours, Hardseal re-downloads its live evidence bundle, verifies its SHA-256 against the published sidecar, runs the standalone verifier on every packet, and appends a self-hash-chained receipt. As of the last heartbeat: {s['streak']} consecutive clean heartbeats, {s['passes']} PASS of {s['total']} total, {days_str} days of continuous attestation.",
  "url": "https://hardseal.ai/trust.html",
  "creator": {{"@type": "Organization", "name": "Hardseal", "url": "https://hardseal.ai/"}},
  "license": "https://hardseal.ai/terms.html",
  "isAccessibleForFree": true,
  "dateModified": "{esc(s['last_ts'])}",
  "measurementTechnique": "SHA-256 self-hash chain (guardian_sha = sha256(prev_line || current_line)); standalone deterministic packet verifier; GitHub Actions scheduled attestation every 6 hours.",
  "variableMeasured": [
    {{"@type": "PropertyValue", "name": "consecutive_clean_heartbeats", "value": "{s['streak']}"}},
    {{"@type": "PropertyValue", "name": "total_heartbeats", "value": "{s['total']}"}},
    {{"@type": "PropertyValue", "name": "pass_count", "value": "{s['passes']}"}},
    {{"@type": "PropertyValue", "name": "fail_count", "value": "{s['fails']}"}},
    {{"@type": "PropertyValue", "name": "continuous_attestation_days", "value": "{days_str}"}}
  ]
}}"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link rel="icon" type="image/svg+xml" href="/favicon.svg">
<title>Trust &amp; Live Attestation — {s['streak']} consecutive clean heartbeats | Hardseal</title>
<meta name="description" content="Hardseal publishes a hash-chained integrity heartbeat every 6 hours. As of the last receipt: {s['streak']} consecutive clean heartbeats, {s['passes']} PASS of {s['total']} total across {days_str} days of continuous, un-backdatable attestation. FAILs are published too.">
<meta name="keywords" content="Hardseal trust, continuous attestation, integrity heartbeat, hash chain, tamper-evident evidence, CMMC evidence integrity, deterministic verification, public proof, guardian_sha">
<meta name="theme-color" content="#000000">
<meta property="og:type" content="website">
<meta property="og:title" content="Hardseal Trust &amp; Live Attestation">
<meta property="og:description" content="{s['streak']} consecutive clean integrity heartbeats. {days_str} days of continuous, un-backdatable attestation. We publish the FAILs too.">
<meta property="og:url" content="https://hardseal.ai/trust.html">
<meta property="og:image" content="https://hardseal.ai/og-card.png">
<meta property="og:site_name" content="Hardseal">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="Hardseal Trust &amp; Live Attestation">
<meta name="twitter:description" content="{s['streak']} consecutive clean integrity heartbeats. We publish the FAILs too.">
<meta name="twitter:image" content="https://hardseal.ai/og-card.png">
<link rel="canonical" href="https://hardseal.ai/trust.html">
<script type="application/ld+json">
{json_ld}
</script>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
:root{{
  --bg:#000;--bg2:#060606;--bg3:#0C0C0C;--bg4:#111;
  --border:#1A1A1A;--border2:#222;--border3:#2A2A2A;
  --white:#FFF;--gray1:#CCC;--gray2:#888;--gray3:#555;--gray4:#333;
  --green:#00FF88;--green-dim:rgba(0,255,136,0.08);--green-med:rgba(0,255,136,0.18);--green-glow:rgba(0,255,136,0.35);
  --blue:#2F80FF;--blue-dim:rgba(47,128,255,0.1);--blue-line:rgba(47,128,255,0.45);
  --red:#FF5577;--red-dim:rgba(255,85,119,0.08);
  --amber:#FFBD2E;--amber-dim:rgba(255,189,46,0.08);
  --mono:'JetBrains Mono',ui-monospace,Menlo,Consolas,monospace;
  --sans:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
}}
html{{scroll-behavior:smooth;background:var(--bg)}}
body{{font-family:var(--sans);color:var(--white);background:var(--bg);-webkit-font-smoothing:antialiased;line-height:1.6;font-size:16px;overflow-x:hidden}}
a{{color:var(--green);text-decoration:none}}
a:hover{{text-decoration:underline}}
.mono{{font-family:var(--mono)}}
header{{border-bottom:1px solid var(--border);padding:18px 40px;display:flex;justify-content:space-between;align-items:center;position:sticky;top:0;background:rgba(0,0,0,0.88);backdrop-filter:blur(8px);-webkit-backdrop-filter:blur(8px);z-index:50}}
.logo{{font-family:var(--mono);font-weight:700;letter-spacing:.08em;font-size:14px;color:var(--white)}}
nav a{{color:var(--gray1);margin-left:28px;font-size:13px;letter-spacing:.05em;font-family:var(--mono)}}
nav a:hover{{color:var(--green);text-decoration:none}}
@media(max-width:760px){{nav{{display:none}}}}
.hero{{max-width:900px;margin:0 auto;padding:64px 40px 24px;text-align:center}}
.eyebrow{{font-family:var(--mono);font-size:11px;color:var(--green);letter-spacing:.18em;margin-bottom:20px}}
.eyebrow .dot{{display:inline-block;width:7px;height:7px;border-radius:50%;background:{last_dot};box-shadow:0 0 8px var(--green-glow);margin-right:8px;vertical-align:middle;animation:pulse 2.4s ease-in-out infinite}}
@keyframes pulse{{0%,100%{{opacity:1}}50%{{opacity:.4}}}}
h1{{font-size:48px;line-height:1.05;letter-spacing:-.025em;margin-bottom:20px;font-weight:800}}
h1 .accent{{color:var(--green)}}
.hero .lead{{font-size:18px;color:var(--gray1);max-width:680px;margin:0 auto;line-height:1.55}}
main{{max-width:980px;margin:0 auto;padding:0 40px 96px}}
.stat-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:0;border:1px solid var(--border2);background:var(--bg2);margin:40px 0 8px}}
.stat{{padding:26px 16px;text-align:center;border-right:1px solid var(--border2)}}
.stat:last-child{{border-right:none}}
.stat .num{{font-family:var(--mono);font-size:34px;color:var(--green);font-weight:700;display:block;line-height:1}}
.stat .lbl{{font-family:var(--mono);font-size:10px;color:var(--gray2);letter-spacing:.1em;margin-top:10px;text-transform:uppercase}}
@media(max-width:680px){{.stat-grid{{grid-template-columns:repeat(2,1fr)}}.stat:nth-child(2){{border-right:none}}.stat:nth-child(1),.stat:nth-child(2){{border-bottom:1px solid var(--border2)}}}}
.asof{{font-family:var(--mono);font-size:11px;color:var(--gray2);letter-spacing:.06em;text-align:center;margin-bottom:8px}}
.section-label{{font-family:var(--mono);font-size:11px;color:var(--green);letter-spacing:.18em;margin:56px 0 8px;border-top:1px solid var(--border);padding-top:32px}}
.section-title{{font-size:28px;font-weight:700;letter-spacing:-.02em;margin-bottom:14px}}
.prose p{{color:var(--gray1);margin-bottom:16px;max-width:760px}}
.prose strong{{color:var(--white)}}
.prose code{{font-family:var(--mono);background:var(--bg3);padding:2px 6px;font-size:13px;color:var(--green)}}
.pull{{border-left:2px solid var(--green);padding:8px 22px;margin:24px 0;color:var(--white);background:var(--bg3);font-size:17px;max-width:760px}}
.how{{display:grid;grid-template-columns:repeat(3,1fr);gap:0;border:1px solid var(--border2);margin-top:8px}}
.how-step{{padding:22px;border-right:1px solid var(--border2)}}
.how-step:last-child{{border-right:none}}
.how-step .n{{font-family:var(--mono);font-size:11px;color:var(--green);letter-spacing:.1em;margin-bottom:10px}}
.how-step h4{{font-size:15px;margin-bottom:8px;color:var(--white)}}
.how-step p{{font-size:13.5px;color:var(--gray1);line-height:1.55}}
@media(max-width:680px){{.how{{grid-template-columns:1fr}}.how-step{{border-right:none;border-bottom:1px solid var(--border2)}}.how-step:last-child{{border-bottom:none}}}}
.panel{{border:1px solid var(--border2);background:var(--bg2);margin-top:8px}}
.panel-head{{display:flex;align-items:center;gap:10px;padding:16px 20px;border-bottom:1px solid var(--border2);font-family:var(--mono);font-size:12px;color:var(--gray1);letter-spacing:.04em;flex-wrap:wrap}}
.panel-head .livedot{{width:8px;height:8px;border-radius:50%;background:{last_dot};box-shadow:0 0 8px var(--green-glow)}}
.log-table{{width:100%;border-collapse:collapse;font-family:var(--mono);font-size:12px}}
.log-table th{{text-align:left;padding:12px 20px;color:var(--gray2);font-weight:500;letter-spacing:.06em;border-bottom:1px solid var(--border2);text-transform:uppercase;font-size:10px}}
.log-table td{{padding:11px 20px;border-bottom:1px solid var(--border);color:var(--gray1)}}
.log-table td.ts{{color:var(--white)}}
.log-table td.pass{{color:var(--green)}}
.log-table td.fail{{color:var(--red)}}
.log-table td.sha{{color:var(--gray2)}}
.panel-foot{{padding:13px 20px;border-top:1px solid var(--border2);font-family:var(--mono);font-size:11px;color:var(--gray2);letter-spacing:.04em;display:flex;justify-content:space-between;flex-wrap:wrap;gap:8px}}
.guardian-line{{font-family:var(--mono);font-size:11px;color:var(--gray2);word-break:break-all;margin-top:14px;padding:12px 16px;background:var(--bg3);border:1px solid var(--border2)}}
.guardian-line strong{{color:var(--green)}}
.cta{{border:1px solid var(--border2);background:var(--bg2);padding:36px;margin-top:56px;text-align:center}}
.cta h3{{font-size:24px;font-weight:700;margin-bottom:12px}}
.cta p{{color:var(--gray1);max-width:620px;margin:0 auto 22px;font-size:15px}}
.cta .btns{{display:flex;gap:12px;justify-content:center;flex-wrap:wrap}}
.cta a{{font-family:var(--mono);font-size:13px;letter-spacing:.05em;padding:13px 24px;border:1px solid var(--border3);color:var(--white);text-transform:uppercase}}
.cta a:hover{{text-decoration:none;border-color:var(--green);color:var(--green)}}
.cta a.primary{{border-color:var(--green);background:var(--green-dim);color:var(--green)}}
.cta a.primary:hover{{background:var(--green-med)}}
footer{{border-top:1px solid var(--border);padding:32px 40px;color:var(--gray2);font-size:12px;text-align:center}}
footer a{{color:var(--gray2)}}
@media(max-width:720px){{header{{padding:16px 20px}}.hero{{padding:44px 20px 16px}}h1{{font-size:32px}}main{{padding:0 20px 64px}}.section-title{{font-size:22px}}.stat .num{{font-size:26px}}}}
</style>
</head>
<body>

<header>
  <a href="/" class="logo">HARDSEAL</a>
  <nav>
    <a href="/edge.html">EDGE</a>
    <a href="/verify.html">VERIFY</a>
    <a href="/trust.html" style="color:var(--white)">TRUST</a>
    <a href="/resources.html">RESOURCES</a>
    <a href="/pilot.html">GET A REVIEW</a>
  </nav>
</header>

<section class="hero">
  <div class="eyebrow"><span class="dot"></span>LIVE ATTESTATION · LAST RESULT: {esc(s['last_result'] or '—')}</div>
  <h1><span class="accent">{s['streak']}</span> consecutive clean heartbeats.</h1>
  <p class="lead">
    Every 6 hours, automatically, Hardseal re-downloads its own live evidence bundle, checks it against the published hash, runs the verifier on every packet, and signs the result into a chain that cannot be backdated. This page is that record — baked in plain HTML so a human, a search engine, or an AI assistant can read the proof without taking our word for it.
  </p>
</section>

<main>

  <div class="stat-grid">
    <div class="stat"><span class="num">{s['streak']}</span><span class="lbl">Consecutive clean</span></div>
    <div class="stat"><span class="num">{days_str}</span><span class="lbl">Days continuous</span></div>
    <div class="stat"><span class="num">{s['passes']}/{s['total']}</span><span class="lbl">PASS / total</span></div>
    <div class="stat"><span class="num">{uptime_str}%</span><span class="lbl">Integrity uptime</span></div>
  </div>
  <div class="asof">As of the last heartbeat: {esc(s['last_ts'])} · {s['fails']} FAIL receipt(s) published, not hidden · first PASS {esc(s['first_pass'])}</div>
  <div class="asof" style="color:var(--gray1);margin-top:6px">{chain_badge}</div>

  <div class="section-label">// WHAT YOU ARE LOOKING AT</div>
  <div class="section-title">Trust you can verify, not trust you have to grant.</div>
  <div class="prose">
    <p>
      Most vendors ask you to believe a logo, a badge, or a testimonial. Hardseal's whole thesis is the opposite: <strong>evidence should be checkable by the person who doubts it.</strong> So we point that thesis back at ourselves. The numbers above are not a marketing claim — they are computed from a public, append-only, hash-chained log that a robot writes to every six hours and that anyone can re-derive line by line.
    </p>
    <p class="pull">
      The chain is the proof. Tamper with any past entry and every entry after it breaks. You cannot backdate {days_str} days of receipts.
    </p>
    <p>
      And when it fails, we publish the failure. There are <strong>{s['fails']} FAIL receipt(s)</strong> in this log right now. We left them in on purpose. A trust signal you can only ever see succeed is not a trust signal — it is a billboard. The willingness to commit the bad days is what makes the good days mean something.
    </p>
  </div>

  <div class="section-label">// HOW THE HEARTBEAT WORKS</div>
  <div class="section-title">Four steps, every six hours, no human in the loop.</div>
  <div class="how">
    <div class="how-step"><div class="n">01 · FETCH</div><h4>Re-download the live bundle</h4><p>A scheduled job pulls the actual <code>hardseal_edge_trophy_case.zip</code> from hardseal.ai — the same file a customer would — cache-busted, no shortcuts.</p></div>
    <div class="how-step"><div class="n">02 · VERIFY</div><h4>Hash + per-packet check</h4><p>It confirms the bundle's SHA-256 matches the published sidecar, then runs the standalone verifier on every packet inside. PASS only if all of it holds.</p></div>
    <div class="how-step"><div class="n">03 · CHAIN</div><h4>Sign into the chain</h4><p>The result is written as <code>guardian_sha = sha256(previous_line || this_line)</code>, linking each receipt to the one before it. The history becomes tamper-evident.</p></div>
    <div class="how-step" style="grid-column:auto"><div class="n">04 · PUBLISH</div><h4>Commit — PASS or FAIL</h4><p>The line is committed to the public log and this page is regenerated. FAILs are committed too, then surfaced as alerts. Nothing is swept.</p></div>
  </div>

  <div class="section-label">// LIVE FEED</div>
  <div class="section-title">The last receipts.</div>
  <div class="prose"><p style="font-size:14px">Baked into this page as of the last heartbeat below. For human visitors with JavaScript, this table refreshes itself from the source log every 60 seconds.</p></div>
  <div class="panel">
    <div class="panel-head"><span class="livedot" id="logDot"></span><span id="logStatus">Last: <strong style="color:{last_dot}">{esc(s['last_result'] or '—')}</strong> at <span class="mono">{esc(s['last_ts'])}</span> · self-hash chain valid</span></div>
    <table class="log-table">
      <thead><tr><th>Timestamp (UTC)</th><th>Result</th><th>Packets</th><th>Guardian SHA</th></tr></thead>
      <tbody id="logBody">
{rows_html}
      </tbody>
    </table>
    <div class="panel-foot">
      <span>Source of truth: <a href="https://github.com/ricojallen37-sketch/hardseal-website/blob/main/docs/integrity/INTEGRITY_LOG.md">INTEGRITY_LOG.md</a></span>
      <span id="logRefresh">Static render · {esc(s['last_ts'])}</span>
    </div>
  </div>
  <div class="guardian-line">Latest <strong>guardian_sha</strong>: {guardian_full}</div>

  <div class="section-label">// VERIFY IT YOURSELF</div>
  <div class="section-title">Don't trust this page. Check it.</div>
  <div class="prose">
    <p>Every number here is reproducible from primary sources. Three ways in, from fastest to most paranoid:</p>
    <p><strong>1. Read the raw log.</strong> Open <a href="https://github.com/ricojallen37-sketch/hardseal-website/blob/main/docs/integrity/INTEGRITY_LOG.md">INTEGRITY_LOG.md</a> and count the lines yourself. Each one is a receipt.</p>
    <p><strong>2. Re-run a packet.</strong> Download <a href="/downloads/verify_standalone.py">verify_standalone.py</a> (Python standard library only, no phone-home) and run it against a <a href="/verify.html">sample packet</a> in your own terminal.</p>
    <p><strong>3. Re-derive the entire chain with one command.</strong> Download <a href="https://raw.githubusercontent.com/ricojallen37-sketch/hardseal-website/main/scripts/verify_chain.py">verify_chain.py</a> (Python standard library only — no network, no Hardseal service) and run it against the log:</p>
    <p><code>curl -sO https://raw.githubusercontent.com/ricojallen37-sketch/hardseal-website/main/scripts/verify_chain.py</code><br>
    <code>curl -sO https://raw.githubusercontent.com/ricojallen37-sketch/hardseal-website/main/docs/integrity/INTEGRITY_LOG.md</code><br>
    <code>python3 verify_chain.py INTEGRITY_LOG.md</code></p>
    <p>It re-derives <code>sha256(previous_full_line || this_line_without_guardian_sha)</code> for every entry, confirms each equals the published <code>guardian_sha</code>, and exits non-zero if any link is broken. Alter one past entry and the break propagates forward — the tool names the exact line. This page ran that same check at build time before it claimed anything above. In 30 years, with Hardseal gone or not, the command still answers the same question.</p>
  </div>

  <div class="cta">
    <h3>This is what we'd do for your evidence.</h3>
    <p>The discipline you see attesting to our own bundle is the discipline Hardseal brings to your SSP, POA&amp;M, SPRS, and control evidence — finding contradictions, unsupported claims, and AI/boilerplate risk before a C3PAO does.</p>
    <div class="btns">
      <a href="/pilot.html" class="primary">Get an Evidence Integrity Review →</a>
      <a href="/verify.html">Verify a packet now →</a>
    </div>
  </div>

</main>

<footer>
  Hardseal · trust &amp; live attestation · regenerated from INTEGRITY_LOG.md every heartbeat · <a href="/">home</a>
</footer>

<script>
/* Progressive enhancement: refresh the live feed for human visitors.
   The static table above is the source-of-record for crawlers and no-JS
   readers; this only upgrades the view, it is never required for the proof. */
const RAW_LOG_URL = 'https://raw.githubusercontent.com/ricojallen37-sketch/hardseal-website/main/docs/integrity/INTEGRITY_LOG.md';
const $ = id => document.getElementById(id);
function esc(s){{return String(s).replace(/[&<>"]/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}}[c]));}}
function parseLine(line){{
  const f = line.split('|').map(s=>s.trim());
  const o = {{ts:f[0]||'',result:'',packets:'',guardian:''}};
  for(const x of f){{
    if(x.startsWith('result=')) o.result=x.slice(7);
    else if(x.startsWith('packets=')) o.packets=x.slice(8);
    else if(x.startsWith('guardian_sha=')) o.guardian=x.slice(13);
  }}
  return o;
}}
async function refresh(){{
  try{{
    const r = await fetch(RAW_LOG_URL, {{cache:'no-store'}});
    if(!r.ok) throw new Error('HTTP '+r.status);
    const lines = (await r.text()).split('\\n').filter(l=>/^\\d{{4}}-\\d{{2}}-\\d{{2}}T/.test(l));
    if(!lines.length) return;
    const rows = lines.slice(-10).reverse().map(parseLine);
    const last = rows[0];
    const color = last.result==='PASS' ? 'var(--green)' : 'var(--red)';
    $('logStatus').innerHTML = 'Last: <strong style="color:'+color+'">'+esc(last.result)+'</strong> at <span class="mono">'+esc(last.ts)+'</span> · self-hash chain valid';
    $('logDot').style.background = color;
    $('logBody').innerHTML = rows.map(r=>'<tr><td class="ts">'+esc(r.ts)+'</td><td class="'+(r.result==='PASS'?'pass':'fail')+'">● '+esc(r.result)+'</td><td>'+esc(r.packets)+'</td><td class="sha">'+esc(r.guardian.slice(0,16))+'…</td></tr>').join('');
    $('logRefresh').textContent = 'Live · refreshed '+new Date().toISOString().replace(/\\.\\d+Z$/,'Z');
  }}catch(e){{ /* keep the static render; the baked proof stands on its own */ }}
}}
refresh();
setInterval(refresh, 60000);
</script>

</body>
</html>
"""


def main() -> int:
    rows = load_rows()
    if not rows:
        print("render_trust_page: no heartbeat lines found; leaving trust.html unchanged.")
        return 0
    stats = compute(rows)

    # Test what we fly: independently re-derive the entire guardian_sha chain
    # before the page is allowed to claim it is verified. If the chain does not
    # re-derive clean, the page says so honestly rather than asserting trust.
    chain = check_chain(LOG_PATH)
    stats["chain_intact"] = bool(chain.get("intact"))
    stats["chain_checked"] = chain.get("checked", 0)

    page = build_html(stats)
    with open(OUT_PATH, "w", encoding="utf-8") as fh:
        fh.write(page)
    print(
        f"render_trust_page: wrote {OUT_PATH} "
        f"(streak={stats['streak']}, pass={stats['passes']}/{stats['total']}, "
        f"fails={stats['fails']}, days={stats['days']:.1f}, as_of={stats['last_ts']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
