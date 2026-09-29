-- Hardseal funnel beacon — D1 schema.
-- One row per (UTC day, allowlisted path, ref slug, two-letter country) tuple.
-- No IPs. No User-Agents. No session IDs. No timestamps finer than the day.
-- That's the entire data model.

CREATE TABLE IF NOT EXISTS beacons (
  day      TEXT    NOT NULL,
  path     TEXT    NOT NULL,
  ref      TEXT    NOT NULL DEFAULT '',
  country  TEXT    NOT NULL DEFAULT '',
  count    INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (day, path, ref, country)
);

CREATE INDEX IF NOT EXISTS beacons_day_idx ON beacons(day);
CREATE INDEX IF NOT EXISTS beacons_ref_idx ON beacons(ref);
