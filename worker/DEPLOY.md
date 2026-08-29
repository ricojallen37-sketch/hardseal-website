# Hardseal Funnel Beacon — Deploy Runbook

**What this is.** A Cloudflare Worker that catches `GET`/`POST` to
`hardseal.ai/api/beacon` and writes one aggregate row to a D1 database.
First-party. No third-party scripts loaded in the visitor's browser. No
cookies. No IP storage. No personal data. The data model is the entire
schema in `schema.sql` — five columns, no exceptions.

**Why a Worker instead of a vendor analytics snippet.** A skeptical CMMC
buyer who opens devtools on `hardseal.ai` will see network requests only
to `hardseal.ai` itself. No `plausible.io`, no `cloudflareinsights.com`,
no third-party domain. The privacy posture is the page-level
architecture, not a policy promise.

**Why Cloudflare and not self-hosting.** D1 + Workers gives a zero-cost
free tier well above what this funnel will ever need (100k requests/day),
no server to patch, and the Worker code is the only place data lands.

---

## One-time setup (Rico's hand)

### 1. Create a Cloudflare account
- Sign up at https://dash.cloudflare.com/sign-up using `rico@hardseal.ai`.
- Add `hardseal.ai` as a zone. Cloudflare will give you two nameservers.
- Update the nameservers at the registrar where `hardseal.ai` is registered.
  DNS propagation is ~minutes; GitHub Pages keeps serving the site during
  the cutover because the existing `CNAME` file at the repo root keeps
  the apex pointed correctly once the DNS record is recreated inside
  Cloudflare (point the apex `@` record at `<your-username>.github.io`
  via a CNAME-flattening / ALIAS record — Cloudflare supports CNAME at
  the apex natively).
- Keep the orange-cloud (proxied) on. That is what lets the Worker route
  intercept `/api/beacon` before GitHub Pages sees it.

### 2. Install Wrangler
```bash
npm install -g wrangler
wrangler login
```

### 3. Create the D1 database
```bash
cd worker
wrangler d1 create hardseal-beacons
```
Copy the printed `database_id` into `wrangler.toml` (replace
`REPLACE_WITH_D1_DATABASE_ID`).

### 4. Apply the schema
```bash
wrangler d1 execute hardseal-beacons --remote --file=./schema.sql
```

### 5. Deploy the worker
```bash
wrangler deploy
```
This will register the route `hardseal.ai/api/beacon`. Confirm in the
Cloudflare dashboard under Workers & Pages → Triggers.

### 6. Verify
- Visit `https://hardseal.ai/p/ir.html?ref=test`. You should land on the
  proof page. In devtools Network, you should see one request to
  `/api/beacon?p=...&ref=test` returning **204 No Content**.
- Read back the row:
  ```bash
  wrangler d1 execute hardseal-beacons --remote --command \
    "SELECT * FROM beacons ORDER BY day DESC LIMIT 20;"
  ```

---

## Querying the funnel

```bash
# Today's hop hits by ref
wrangler d1 execute hardseal-beacons --remote --command \
  "SELECT ref, SUM(count) AS hits FROM beacons \
   WHERE day = date('now') AND path = '/p/ir.html' \
   GROUP BY ref ORDER BY hits DESC;"

# Marketing page views, last 7 days
wrangler d1 execute hardseal-beacons --remote --command \
  "SELECT path, SUM(count) AS views FROM beacons \
   WHERE day >= date('now','-7 days') AND path != '/_other' \
   GROUP BY path ORDER BY views DESC;"
```

---

## What the Worker does NOT do

- Does not set a cookie. Does not read a cookie. Does not return one.
- Does not record IP address, User-Agent, referrer header, screen size,
  language, timezone, or anything else not in `schema.sql`.
- Does not log requests anywhere outside the D1 table — no Cloudflare
  Logpush, no R2 archive, no Workers Logs persistence.
- Does not respond with any body. Always returns 204.
- Does not run on the verifier (`/verify.html`) or anything under
  `/proof/`. Those pages never load `beacon.js` and never call
  `/api/beacon`. The proof page's "0 network calls" guarantee is
  preserved at the architectural level — not by a policy promise.

---

## Disabling the beacon (panic switch)

If you ever need to kill measurement instantly:

```bash
cd worker && wrangler delete   # removes the Worker; /api/beacon returns 404
```

The site continues to function — `beacon.js` swallows the 404 and the
hop page still redirects. No prospect-visible behavior changes.
