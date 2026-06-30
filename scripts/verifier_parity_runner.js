/* Parity runner: emit the JS verifier's verdict + recomputed chain root
 * for one receipt file as JSON, for comparison against the canonical
 * Python verifier. Used by scripts/verifier_parity.py. Node, no deps. */
const path = require("path");
const fs = require("fs");
const V = require(path.join(__dirname, "..", "assets", "hardseal-verifier.js"));

(async () => {
  const file = process.argv[2];
  let out;
  try {
    const text = fs.readFileSync(file, "utf8");
    const r = await V.verify(text);
    out = { passed: !!r.passed, root: r.recomputedRoot || null, format: r.format || null };
  } catch (e) {
    out = { passed: false, root: null, format: null, error: String((e && e.message) || e) };
  }
  process.stdout.write(JSON.stringify(out));
})();
