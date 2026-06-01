"""
Import GPS tracks, positions and charge sessions from HA MariaDB export.

Input:  /tmp/ha_states.tsv  (tab-separated: ts, entity_id, state, shared_attrs)
Output: updates LeapMotor Mate SQLite DB with:
        - trip_positions  linked to existing trips
        - start/end GPS on trips
        - charge sessions derived from charging_power > 0 periods
"""
import json
import re
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path

TSV_FILE = Path("/tmp/ha_states.tsv")
LM_DB    = Path("/Users/silviobressani/leapmotor-mate/leapmotor_mate.db")
BATTERY_KWH = 67.1


def parse_ts(s: str) -> datetime:
    s = s.strip().replace(" ", "T")
    if "." in s:
        s = s[:26]
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def load_tsv(path: Path) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8") as f:
        headers = f.readline().strip().split("\t")
        for line in f:
            parts = line.rstrip("\n").split("\t", 3)
            if len(parts) < 3:
                continue
            row = dict(zip(headers, parts))
            row["_ts"] = parse_ts(row["ts"])
            rows.append(row)
    print(f"Loaded {len(rows):,} rows from TSV")
    return rows


def build_timeline(rows: list[dict]) -> dict:
    """Build per-entity sorted timeline."""
    tl: dict[str, list] = {}
    for r in rows:
        e = r["entity_id"]
        tl.setdefault(e, []).append(r)
    for e in tl:
        tl[e].sort(key=lambda x: x["_ts"])
    return tl


def get_nearest(timeline: list[dict], ts: datetime) -> dict | None:
    """Binary-search nearest record to ts."""
    if not timeline:
        return None
    lo, hi = 0, len(timeline) - 1
    while lo < hi:
        mid = (lo + hi) // 2
        if timeline[mid]["_ts"] < ts:
            lo = mid + 1
        else:
            hi = mid
    # Check both sides
    candidates = [timeline[lo]]
    if lo > 0:
        candidates.append(timeline[lo - 1])
    return min(candidates, key=lambda r: abs((r["_ts"] - ts).total_seconds()))


def extract_gps(row: dict) -> tuple[float, float] | None:
    try:
        attrs = json.loads(row.get("shared_attrs") or "{}")
        lat = attrs.get("latitude") or attrs.get("raw_latitude")
        lon = attrs.get("longitude") or attrs.get("raw_longitude")
        if lat and lon:
            return float(lat), float(lon)
    except Exception:
        pass
    return None


def main():
    rows = load_tsv(TSV_FILE)
    tl   = build_timeline(rows)

    lm = sqlite3.connect(LM_DB)
    lm.row_factory = sqlite3.Row

    vehicle = lm.execute("SELECT id FROM vehicles LIMIT 1").fetchone()
    if not vehicle:
        print("ERROR: No vehicle found — run the poller first"); return
    vehicle_id = vehicle["id"]
    battery_capacity = float(lm.execute(
        "SELECT value FROM settings WHERE key='battery_capacity_kwh'"
    ).fetchone()["value"])

    # ── 1. GPS TRACKS for existing trips ──────────────────────────────────────
    print("\n=== Importing GPS tracks for trips ===")
    trips = lm.execute(
        "SELECT * FROM trips WHERE vehicle_id=? AND ended_at IS NOT NULL ORDER BY started_at",
        (vehicle_id,)
    ).fetchall()

    gps_tl    = tl.get("device_tracker.leapmotor_location", [])
    speed_tl  = tl.get("sensor.leapmotor_speed", [])
    soc_tl    = tl.get("sensor.leapmotor_precise_battery", [])

    trips_updated = 0
    positions_added = 0

    for trip in trips:
        t_start = parse_ts(trip["started_at"])
        t_end   = parse_ts(trip["ended_at"])

        # GPS positions within trip window
        trip_gps = [
            r for r in gps_tl
            if t_start <= r["_ts"] <= t_end + timedelta(minutes=2)
        ]

        if not trip_gps:
            continue

        # Clear old positions for this trip (re-import)
        lm.execute("DELETE FROM trip_positions WHERE trip_id=?", (trip["id"],))

        for g in trip_gps:
            coords = extract_gps(g)
            if not coords:
                continue
            lat, lon = coords

            # Get nearest speed and SOC
            spd_row = get_nearest(speed_tl, g["_ts"])
            soc_row = get_nearest(soc_tl,   g["_ts"])
            spd = float(spd_row["state"]) if spd_row and spd_row["state"] not in ("unavailable","unknown") else None
            soc = float(soc_row["state"]) if soc_row and soc_row["state"] not in ("unavailable","unknown") else None

            lm.execute(
                """INSERT INTO trip_positions (trip_id, recorded_at, latitude, longitude, speed_kmh, soc)
                   VALUES (?,?,?,?,?,?)""",
                (trip["id"], g["_ts"].isoformat(), lat, lon, spd, soc)
            )
            positions_added += 1

        # Update start/end GPS on trip
        first_gps = extract_gps(trip_gps[0])
        last_gps  = extract_gps(trip_gps[-1])
        if first_gps:
            lm.execute("UPDATE trips SET start_lat=?,start_lon=? WHERE id=?",
                        (*first_gps, trip["id"]))
        if last_gps:
            lm.execute("UPDATE trips SET end_lat=?,end_lon=? WHERE id=?",
                        (*last_gps, trip["id"]))

        trips_updated += 1

    lm.commit()
    print(f"Updated {trips_updated} trips with GPS | {positions_added} positions added")

    # ── 2. CHARGE SESSIONS from charging_power > 0 ────────────────────────────
    print("\n=== Importing charge sessions ===")

    charge_tl = tl.get("sensor.leapmotor_charging_power", [])
    soc_tl    = tl.get("sensor.leapmotor_precise_battery", [])

    # Find contiguous charging periods (power > 0)
    charge_sessions = []
    in_charge = False
    session_start = None
    session_rows  = []

    for r in charge_tl:
        try:
            pwr = float(r["state"])
        except (ValueError, TypeError):
            pwr = 0.0

        if pwr > 0:
            if not in_charge:
                in_charge     = True
                session_start = r["_ts"]
                session_rows  = [r]
            else:
                session_rows.append(r)
        else:
            if in_charge and session_rows:
                duration_min = (session_rows[-1]["_ts"] - session_start).total_seconds() / 60
                if duration_min >= 3:  # ignore < 3 min blips
                    charge_sessions.append({
                        "started_at": session_start,
                        "ended_at":   session_rows[-1]["_ts"],
                        "rows":       session_rows,
                    })
            in_charge     = False
            session_rows  = []

    print(f"Found {len(charge_sessions)} charge sessions in HA history")

    # Check existing charges to avoid duplicates
    existing_charge_starts = {
        parse_ts(r[0]) for r in lm.execute("SELECT started_at FROM charges").fetchall()
    }

    charges_imported = 0
    for cs in charge_sessions:
        # Skip if within 10 min of an existing charge
        if any(abs((cs["started_at"] - ex).total_seconds()) < 600 for ex in existing_charge_starts):
            continue

        # Get SOC at start and end
        soc_start_row = get_nearest(soc_tl, cs["started_at"])
        soc_end_row   = get_nearest(soc_tl, cs["ended_at"])
        soc_start = float(soc_start_row["state"]) if soc_start_row else None
        soc_end   = float(soc_end_row["state"])   if soc_end_row   else None

        energy_kwh = ((soc_end - soc_start) / 100 * battery_capacity) if (soc_start and soc_end) else None

        # Peak power and charge type
        powers = []
        for r in cs["rows"]:
            try: powers.append(float(r["state"]))
            except: pass
        max_power = max(powers) if powers else 0
        charge_type = "DC" if max_power > 11 else "AC"

        # GPS at charge location
        gps_row = get_nearest(gps_tl, cs["started_at"])
        coords  = extract_gps(gps_row) if gps_row else None
        lat = coords[0] if coords else None
        lon = coords[1] if coords else None

        duration_min = (cs["ended_at"] - cs["started_at"]).total_seconds() / 60

        lm.execute(
            """INSERT INTO charges
               (vehicle_id, started_at, ended_at, start_soc, end_soc,
                energy_added_kwh, duration_min, latitude, longitude,
                charge_type, max_power_kw)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                vehicle_id,
                cs["started_at"].isoformat(), cs["ended_at"].isoformat(),
                soc_start, soc_end,
                round(max(energy_kwh, 0), 3) if energy_kwh else None,
                round(duration_min, 1),
                lat, lon, charge_type, round(max_power, 2),
            )
        )
        charges_imported += 1

    lm.commit()
    print(f"Imported {charges_imported} charge sessions")

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n=== Final DB state ===")
    print(f"Trips:           {lm.execute('SELECT COUNT(*) FROM trips').fetchone()[0]}")
    print(f"Trip positions:  {lm.execute('SELECT COUNT(*) FROM trip_positions').fetchone()[0]}")
    print(f"Charges:         {lm.execute('SELECT COUNT(*) FROM charges').fetchone()[0]}")
    print(f"Positions:       {lm.execute('SELECT COUNT(*) FROM positions').fetchone()[0]}")

    lm.close()


if __name__ == "__main__":
    main()
