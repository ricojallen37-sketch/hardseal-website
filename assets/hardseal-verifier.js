/* ----------------------------------------------------------------------
 * Hardseal — reusable client-side packet/receipt verifier
 * ----------------------------------------------------------------------
 * One module, two formats:
 *   - "cmmc"  native CMMC packet-QA receipts (the $5,500 review deliverable)
 *             port of downloads/verify_cmmc_packet_qa.py
 *   - "edge"  Hardseal Edge inference packets
 *             port of downloads/verify_standalone.py (same logic as verify.html)
 *
 * Byte-identical canonical JSON to Python json.dumps(sort_keys=True,
 * ensure_ascii=True, separators=(",",":")). Numbers are preserved as their
 * original source tokens so 43.0 stays "43.0" (Python keeps int/float; a
 * naive JSON.parse would not).
 *
 * Public API (window.HardsealVerifier):
 *   parse(text)            -> number-preserving parsed object
 *   canonicalJson(obj)     -> canonical JSON string
 *   detectFormat(obj)      -> "cmmc" | "edge" | null
 *   verify(textOrObject)   -> Promise<NormalizedResult>
 *   summarize(obj, format) -> plain-English summary object
 *
 * NormalizedResult:
 *   { passed, format, passes:[], failures:[], chainRoot, recomputedRoot,
 *     packet, summary }
 * -------------------------------------------------------------------- */
(function (global) {
  "use strict";

  // --- number-preserving JSON parser -----------------------------------
  function NumTok(s) { this.__num = s; }

  function parsePreservingNumbers(text) {
    let i = 0;
    const skip = () => { while (i < text.length && /\s/.test(text[i])) i++; };
    const err = (msg) => { throw new Error(`JSON parse at ${i}: ${msg} near "${text.slice(Math.max(0, i - 20), i + 20)}"`); };
    function parseValue() {
      skip();
      const c = text[i];
      if (c === "{") return parseObject();
      if (c === "[") return parseArray();
      if (c === '"') return parseString();
      if (c === "t" || c === "f") return parseBool();
      if (c === "n") return parseNull();
      if (c === "-" || (c >= "0" && c <= "9")) return parseNumber();
      err("unexpected '" + c + "'");
    }
    function parseObject() {
      i++; skip();
      const obj = {};
      if (text[i] === "}") { i++; return obj; }
      while (true) {
        skip(); const k = parseString(); skip();
        if (text[i] !== ":") err("expected :");
        i++;
        obj[k] = parseValue();
        skip();
        if (text[i] === ",") { i++; continue; }
        if (text[i] === "}") { i++; return obj; }
        err("expected , or }");
      }
    }
    function parseArray() {
      i++; skip();
      const arr = [];
      if (text[i] === "]") { i++; return arr; }
      while (true) {
        arr.push(parseValue()); skip();
        if (text[i] === ",") { i++; continue; }
        if (text[i] === "]") { i++; return arr; }
        err("expected , or ]");
      }
    }
    function parseString() {
      if (text[i] !== '"') err('expected "');
      i++;
      let s = "";
      while (i < text.length && text[i] !== '"') {
        if (text[i] === "\\") {
          i++; const e = text[i++];
          if (e === '"') s += '"';
          else if (e === "\\") s += "\\";
          else if (e === "/") s += "/";
          else if (e === "b") s += "\b";
          else if (e === "f") s += "\f";
          else if (e === "n") s += "\n";
          else if (e === "r") s += "\r";
          else if (e === "t") s += "\t";
          else if (e === "u") { s += String.fromCharCode(parseInt(text.slice(i, i + 4), 16)); i += 4; }
          else err("bad escape \\" + e);
        } else { s += text[i++]; }
      }
      if (text[i] !== '"') err("unterminated string");
      i++;
      return s;
    }
    function parseBool() {
      if (text.slice(i, i + 4) === "true") { i += 4; return true; }
      if (text.slice(i, i + 5) === "false") { i += 5; return false; }
      err("expected bool");
    }
    function parseNull() {
      if (text.slice(i, i + 4) === "null") { i += 4; return null; }
      err("expected null");
    }
    function parseNumber() {
      const start = i;
      if (text[i] === "-") i++;
      while (i < text.length && text[i] >= "0" && text[i] <= "9") i++;
      if (text[i] === ".") { i++; while (i < text.length && text[i] >= "0" && text[i] <= "9") i++; }
      if (text[i] === "e" || text[i] === "E") {
        i++;
        if (text[i] === "+" || text[i] === "-") i++;
        while (i < text.length && text[i] >= "0" && text[i] <= "9") i++;
      }
      return new NumTok(text.slice(start, i));
    }
    const v = parseValue(); skip();
    if (i !== text.length) err("trailing characters");
    return v;
  }

  // --- canonical JSON (matches Python json.dumps canonical form) -------
  function jsonStringEscapeAscii(s) {
    let out = '"';
    for (let i = 0; i < s.length; i++) {
      const c = s.charCodeAt(i);
      if (c === 0x22) out += '\\"';
      else if (c === 0x5c) out += "\\\\";
      else if (c === 0x08) out += "\\b";
      else if (c === 0x0c) out += "\\f";
      else if (c === 0x0a) out += "\\n";
      else if (c === 0x0d) out += "\\r";
      else if (c === 0x09) out += "\\t";
      else if (c < 0x20 || c > 0x7e) out += "\\u" + ("0000" + c.toString(16)).slice(-4);
      else out += s[i];
    }
    return out + '"';
  }

  function canonicalJson(obj) {
    if (obj === null) return "null";
    if (obj instanceof NumTok) return obj.__num;
    if (typeof obj === "boolean") return obj ? "true" : "false";
    if (typeof obj === "number") {
      if (!isFinite(obj)) throw new Error("non-finite number in packet");
      return JSON.stringify(obj);
    }
    if (typeof obj === "string") return jsonStringEscapeAscii(obj);
    if (Array.isArray(obj)) return "[" + obj.map(canonicalJson).join(",") + "]";
    if (typeof obj === "object") {
      const keys = Object.keys(obj).sort();
      return "{" + keys.map((k) => jsonStringEscapeAscii(k) + ":" + canonicalJson(obj[k])).join(",") + "}";
    }
    throw new Error("unsupported type in packet: " + typeof obj);
  }

  // --- crypto helpers --------------------------------------------------
  const _crypto = (global.crypto && global.crypto.subtle) ? global.crypto
    : (typeof require === "function" ? require("crypto").webcrypto : null);

  function utf8(s) { return new TextEncoder().encode(s); }

  async function sha256Hex(bytes) {
    const buf = await _crypto.subtle.digest("SHA-256", bytes);
    return Array.from(new Uint8Array(buf)).map((b) => b.toString(16).padStart(2, "0")).join("");
  }

  function concatBytes(a, b) {
    const out = new Uint8Array(a.length + b.length);
    out.set(a, 0); out.set(b, a.length);
    return out;
  }

  // shared banned-claim scan
  function scanForBanned(node, phrases, path) {
    path = path || "";
    const hits = [];
    if (typeof node === "string") {
      const lower = node.toLowerCase();
      for (const phrase of phrases) {
        if (lower.includes(phrase)) hits.push(`${path || "<root>"}: contains banned phrase '${phrase}'`);
      }
    } else if (Array.isArray(node)) {
      node.forEach((v, i) => hits.push(...scanForBanned(v, phrases, `${path}[${i}]`)));
    } else if (node && typeof node === "object") {
      for (const k of Object.keys(node)) hits.push(...scanForBanned(node[k], phrases, path ? `${path}.${k}` : k));
    }
    return hits;
  }

  // ====================================================================
  // CMMC packet-QA receipt verifier (port of verify_cmmc_packet_qa.py)
  // ====================================================================
  const CMMC = {
    GENESIS: "HARDSEAL_CMMC_PACKET_QA_RECEIPT_v1",
    RECEIPT_TYPE: "hardseal_cmmc_packet_qa_receipt",
    SCHEMA: "0.1",
    ALGO: "sha256_canonical_json_chain_v1",
    SECTION_ORDER: ["metadata", "framework_basis", "packet_slice", "packet_claim", "evidence_observed", "finding", "reviewer_question", "next_proof_needed", "limitations"],
    REQUIRED_TOP: ["receipt_type", "schema_version", "receipt_id", "created_utc", "offline_mode", "sections", "integrity"],
    REQUIRED_INTEGRITY: ["hash_chain_algorithm", "genesis_label", "section_order", "section_hashes", "chain_root", "tamper_status", "verification_command"],
    BANNED: ["we certify", "hardseal certifies", "hardseal assesses", "certified compliant", "compliance-equivalent", "assessor-equivalent", "equivalent to a c3pao", "endorsed by cyber ab", "guaranteed pass", "guaranteed compliant", "accepted by c3pao", "assessor-ready"]
  };

  async function cmmcSeed(r) {
    const payload = {
      genesis_label: CMMC.GENESIS,
      receipt_type: r.receipt_type,
      schema_version: r.schema_version,
      receipt_id: r.receipt_id,
      created_utc: r.created_utc,
      offline_mode: r.offline_mode
    };
    return sha256Hex(utf8(canonicalJson(payload)));
  }

  async function cmmcCompute(r) {
    const sections = r.sections;
    let previous = await cmmcSeed(r);
    const sectionHashes = [];
    for (const section of CMMC.SECTION_ORDER) {
      if (!(section in sections)) throw new Error("missing receipt section: " + section);
      const payload = { section: section, payload: sections[section], previous_hash: previous };
      const current = await sha256Hex(utf8(canonicalJson(payload)));
      sectionHashes.push({ section: section, hash: current });
      previous = current;
    }
    return { chainRoot: previous, sectionHashes: sectionHashes };
  }

  async function cmmcVerify(r) {
    const passes = [], failures = [];
    let recomputedRoot = null;

    const missingTop = CMMC.REQUIRED_TOP.filter((f) => !(f in r));
    if (missingTop.length) failures.push(`missing top-level fields: [${missingTop.join(", ")}]`);
    else passes.push("top-level fields complete");

    if (r.receipt_type !== CMMC.RECEIPT_TYPE) failures.push(`unsupported receipt_type: ${r.receipt_type}`);
    else passes.push("receipt_type recognized");

    if (r.schema_version !== CMMC.SCHEMA) failures.push(`unsupported schema_version: ${r.schema_version}`);
    else passes.push("schema_version supported");

    if (typeof r.offline_mode !== "boolean") failures.push("offline_mode missing or not a bool");
    else passes.push("offline mode declared");

    const sections = r.sections;
    if (!sections || typeof sections !== "object" || Array.isArray(sections)) {
      failures.push("sections missing or not an object");
      return finalize("cmmc", passes, failures, r, recomputedRoot);
    }
    const missingSections = CMMC.SECTION_ORDER.filter((s) => !(s in sections));
    const extraSections = Object.keys(sections).filter((s) => CMMC.SECTION_ORDER.indexOf(s) === -1).sort();
    if (missingSections.length) failures.push(`missing sections: [${missingSections.join(", ")}]`);
    else if (extraSections.length) failures.push(`unexpected sections: [${extraSections.join(", ")}]`);
    else passes.push("required sections present");

    const integrity = r.integrity;
    if (!integrity || typeof integrity !== "object") {
      failures.push("integrity block missing or not an object");
      return finalize("cmmc", passes, failures, r, recomputedRoot);
    }
    const missingIntegrity = CMMC.REQUIRED_INTEGRITY.filter((f) => !(f in integrity));
    if (missingIntegrity.length) failures.push(`integrity block missing fields: [${missingIntegrity.join(", ")}]`);
    else passes.push("integrity fields complete");

    if (integrity.hash_chain_algorithm !== CMMC.ALGO) failures.push(`unsupported hash_chain_algorithm: ${integrity.hash_chain_algorithm}`);
    else passes.push("hash algorithm supported");

    if (integrity.genesis_label !== CMMC.GENESIS) failures.push(`unexpected genesis_label: ${integrity.genesis_label}`);
    else passes.push("genesis label recognized");

    if (canonicalJson(integrity.section_order || null) !== canonicalJson(CMMC.SECTION_ORDER)) failures.push("section_order does not match verifier contract");
    else passes.push("section order fixed");

    if (!missingTop.length && !missingSections.length && !missingIntegrity.length) {
      try {
        const { chainRoot, sectionHashes } = await cmmcCompute(r);
        recomputedRoot = chainRoot;
        const storedRoot = integrity.chain_root;
        const storedHashes = integrity.section_hashes;
        if (storedRoot !== chainRoot) {
          const firstBad = firstBadSection(storedHashes, sectionHashes);
          failures.push(`chain root mismatch.${firstBad ? " first_mutated_section=" + firstBad : ""}`);
        } else if (canonicalJson(storedHashes) !== canonicalJson(sectionHashes)) {
          failures.push("section_hashes mismatch while chain_root matches");
        } else {
          passes.push("hash chain valid");
        }
      } catch (e) {
        failures.push("chain recomputation failed: " + e.message);
      }
    }

    const hits = scanForBanned(r, CMMC.BANNED);
    if (hits.length) hits.forEach((h) => failures.push("banned phrase: " + h));
    else passes.push("no banned claim language detected");

    return finalize("cmmc", passes, failures, r, recomputedRoot);
  }

  function firstBadSection(stored, recomputed) {
    if (!Array.isArray(stored)) return null;
    const n = Math.min(stored.length, recomputed.length);
    for (let i = 0; i < n; i++) {
      const s = stored[i], rcomp = recomputed[i];
      if (!s || typeof s !== "object") return rcomp.section;
      if (s.section !== rcomp.section) return rcomp.section;
      if (s.hash !== rcomp.hash) return rcomp.section;
    }
    if (stored.length !== recomputed.length) return recomputed[Math.min(stored.length, recomputed.length - 1)].section;
    return null;
  }

  // ====================================================================
  // Edge inference packet verifier (port of verify_standalone.py)
  // ====================================================================
  const EDGE = {
    GENESIS: "HARDSEAL_EDGE_GENESIS_v1",
    SECTION_ORDER: ["device", "model", "benchmark", "sensors", "limitations"],
    REQUIRED_HEADER: ["packet_type", "schema_version", "operational_class", "session_id", "created_utc", "offline_mode", "doctrine_url"],
    REQUIRED_INTEGRITY: ["hash_chain_algorithm", "hash_chain_root", "section_hashes", "tamper_status", "verification_command"],
    SCHEMA: ["1.0"],
    OPCLASS: ["edge-inference-verification"],
    BANNED: ["we certify", "hardseal certifies", "hardseal assesses", "certified compliant", "compliance-equivalent", "assessor-equivalent", "equivalent to a c3pao", "endorsed by cyber ab", "faa-approved", "autonomy assurance certified", "drone certified", "guaranteed safe", "guaranteed correct", "guaranteed mission"]
  };

  async function edgeSeed(p) {
    const parts = [EDGE.GENESIS, p.packet_type, p.schema_version, p.operational_class, p.session_id, p.created_utc, String(p.offline_mode).toLowerCase()];
    return sha256Hex(utf8(parts.join("||")));
  }

  async function edgeCompute(p) {
    let prev = await edgeSeed(p);
    const pairs = [];
    for (const name of EDGE.SECTION_ORDER) {
      if (!(name in p)) throw new Error("hash chain missing required section: '" + name + "'");
      const sectionBytes = utf8(canonicalJson(p[name]));
      const combined = concatBytes(sectionBytes, utf8(prev));
      const h = await sha256Hex(combined);
      pairs.push([name, h]);
      prev = h;
    }
    return { chainRoot: pairs[pairs.length - 1][1], pairs };
  }

  async function edgeVerify(p) {
    const passes = [], failures = [];
    let recomputedRoot = null;

    const missingHeader = EDGE.REQUIRED_HEADER.filter((f) => !(f in p));
    if (missingHeader.length) failures.push(`missing header fields: [${missingHeader.join(", ")}]`);
    else passes.push("header fields complete");

    if (!EDGE.SCHEMA.includes(p.schema_version)) failures.push(`schema_version '${p.schema_version}' not supported`);
    else passes.push("schema_version supported");

    if (!EDGE.OPCLASS.includes(p.operational_class)) failures.push(`operational_class '${p.operational_class}' not recognized`);
    else passes.push("operational_class recognized");

    const missingSections = EDGE.SECTION_ORDER.filter((s) => !(s in p));
    if (missingSections.length) failures.push(`missing sections: [${missingSections.join(", ")}]`);
    else passes.push("required sections present");

    const engineSha = (p.model && p.model.engine_sha256) || "";
    if (!engineSha || engineSha.length !== 64) failures.push("model.engine_sha256 missing or not a 64-char hex SHA-256 digest");
    else passes.push("engine SHA-256 present");

    if (typeof p.offline_mode !== "boolean") failures.push("offline_mode missing or not a bool");
    else passes.push("offline mode declared");

    const integrity = p.integrity;
    if (!integrity || typeof integrity !== "object") {
      failures.push("integrity block missing or not an object");
      return finalize("edge", passes, failures, p, recomputedRoot);
    }
    const missingIntegrity = EDGE.REQUIRED_INTEGRITY.filter((f) => !(f in integrity));
    if (missingIntegrity.length) failures.push(`integrity block missing fields: [${missingIntegrity.join(", ")}]`);

    if (!missingHeader.length && !missingSections.length && !missingIntegrity.length) {
      try {
        const { chainRoot, pairs } = await edgeCompute(p);
        recomputedRoot = chainRoot;
        const storedRoot = integrity.hash_chain_root;
        const storedPairs = integrity.section_hashes;
        let sectionPairsOK = true, detail = null;
        if (!Array.isArray(storedPairs)) { sectionPairsOK = false; detail = "section_hashes is not a list"; }
        else if (storedPairs.length !== pairs.length) { sectionPairsOK = false; detail = `section_hashes length ${storedPairs.length} != expected ${pairs.length}`; }
        else {
          for (let i = 0; i < pairs.length; i++) {
            const [name, recomputed] = pairs[i];
            const stored = storedPairs[i];
            if (!stored || typeof stored !== "object") { sectionPairsOK = false; detail = `entry for '${name}' is not a dict`; break; }
            if (stored.section !== name) { sectionPairsOK = false; detail = `name mismatch at '${name}'`; break; }
            if (stored.hash !== recomputed) { sectionPairsOK = false; detail = `hash mismatch at '${name}'`; break; }
          }
        }
        if (storedRoot !== chainRoot) {
          let firstBad = null;
          if (Array.isArray(storedPairs) && storedPairs.length === pairs.length) {
            for (let i = 0; i < pairs.length; i++) {
              const stored = storedPairs[i]; const [name, recomputed] = pairs[i];
              if (!stored || typeof stored !== "object") { firstBad = name; break; }
              if (stored.hash !== recomputed) { firstBad = stored.section || name; break; }
            }
          }
          failures.push(`hash chain INVALID — recomputed root does not match stored root${firstBad ? " (first mutated section: " + firstBad + ")" : ""}`);
        } else if (!sectionPairsOK) {
          failures.push("section_hashes INVALID — chain root matches but stored section_hashes diverge: " + detail);
        } else {
          passes.push("hash chain valid");
        }
      } catch (e) {
        failures.push("chain recomputation failed: " + e.message);
      }
    }

    const hits = scanForBanned(p, EDGE.BANNED);
    if (hits.length) hits.forEach((h) => failures.push("banned phrase: " + h));
    else passes.push("no banned legal language detected");

    return finalize("edge", passes, failures, p, recomputedRoot);
  }

  // --- normalization + summary ----------------------------------------
  function finalize(format, passes, failures, packet, recomputedRoot) {
    const stored = format === "cmmc"
      ? (packet.integrity && packet.integrity.chain_root)
      : (packet.integrity && packet.integrity.hash_chain_root);
    return {
      passed: failures.length === 0,
      format: format,
      passes: passes,
      failures: failures,
      chainRoot: stored || null,
      recomputedRoot: recomputedRoot,
      packet: packet,
      summary: summarize(packet, format)
    };
  }

  // strip NumTok back to plain values for display
  function plain(v) {
    if (v instanceof NumTok) return v.__num;
    if (Array.isArray(v)) return v.map(plain);
    if (v && typeof v === "object") {
      const o = {};
      for (const k of Object.keys(v)) o[k] = plain(v[k]);
      return o;
    }
    return v;
  }

  function summarize(p, format) {
    if (format === "cmmc") {
      const s = p.sections || {};
      const fb = s.framework_basis || {};
      const ctrl = fb.control || {};
      const finding = s.finding || {};
      const lim = s.limitations || {};
      return {
        title: (s.metadata && s.metadata.receipt_name) || p.receipt_id || "CMMC Packet QA Receipt",
        control: ctrl.id ? `${ctrl.id}${ctrl.requirement ? " — " + ctrl.requirement : ""}` : (fb.framework || ""),
        framework: fb.framework || "",
        findingStatus: finding.status || "",
        findingText: finding.finding_text || "",
        proves: plain(lim.what_pass_proves || []),
        doesNotProve: plain(lim.what_pass_does_not_prove || []),
        claimBoundary: lim.claim_boundary || "",
        receiptId: p.receipt_id || "",
        created: p.created_utc || "",
        offline: p.offline_mode === true
      };
    }
    // edge
    const model = p.model || {};
    return {
      title: "Hardseal Edge Session " + (p.session_id || ""),
      control: (p.operational_class || "edge-inference-verification"),
      framework: "Hardseal Edge",
      findingStatus: (p.integrity && p.integrity.tamper_status) || "",
      findingText: model.name ? `Edge inference packet for model ${model.name} (${model.precision || ""}).` : "Hardseal Edge inference packet.",
      proves: ["The packet sections still match the recorded SHA-256 chain root.", "The benchmark, device, model, and sensor records were not changed after sealing."],
      doesNotProve: plain((p.limitations) || []),
      claimBoundary: "Hardseal Edge records integrity of an offline inference session under explicit limitations.",
      receiptId: p.session_id || "",
      created: p.created_utc || "",
      offline: p.offline_mode === true
    };
  }

  // --- dispatch --------------------------------------------------------
  function detectFormat(p) {
    if (!p || typeof p !== "object") return null;
    if (p.receipt_type === CMMC.RECEIPT_TYPE) return "cmmc";
    if (p.integrity && p.integrity.hash_chain_algorithm === CMMC.ALGO) return "cmmc";
    if (p.packet_type === "hardseal_edge_session") return "edge";
    if (p.integrity && "hash_chain_root" in p.integrity) return "edge";
    return null;
  }

  async function verify(input) {
    if (!_crypto || !_crypto.subtle) throw new Error("WebCrypto SHA-256 unavailable in this environment");
    const obj = typeof input === "string" ? parsePreservingNumbers(input) : input;
    const fmt = detectFormat(obj);
    if (fmt === "cmmc") return cmmcVerify(obj);
    if (fmt === "edge") return edgeVerify(obj);
    return {
      passed: false, format: null, passes: [],
      failures: ["unrecognized packet format (not a Hardseal CMMC receipt or Edge packet)"],
      chainRoot: null, recomputedRoot: null, packet: obj, summary: null
    };
  }

  const api = { verify, parse: parsePreservingNumbers, canonicalJson, detectFormat, summarize, NumTok };
  global.HardsealVerifier = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof window !== "undefined" ? window : globalThis);
