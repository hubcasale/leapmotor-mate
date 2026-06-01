"""
Import trip history from HA leapmotor_trip.db into LeapMotor Mate.

HA schema:  id, start, end, durata, km_start, km_end, km, kwh, cons,
            soc_start, soc_end, vel_media, temperatura, note
LM schema:  id, vehicle_id, started_at, ended_at, start_lat, start_lon,
            end_lat, end_lon, distance_km, start_soc, end_soc,
            start_odometer_km, end_odometer_km, regen_kwh,
            duration_min, efficiency_kwh_100km
"""
import sqlite3
import sys
from pathlib import Path

HA_DB   = Path("/tmp/leapmotor_ha_trips.db")
LM_DB   = Path("/Users/silviobressani/leapmotor-mate/leapmotor_mate.db")


def parse_duration(s: str) -> float:
    """'00:14' or '01:23' → minutes as float."""
    try:
        parts = str(s).strip().split(":")
        return int(parts[0]) * 60 + int(parts[1])
    except Exception:
        return 0.0


def to_iso(s: str) -> str:
    """'2026-05-19 18:34:56' → ISO 8601 with UTC marker."""
    return str(s).replace(" ", "T") + "+00:00" if s else None


def main():
    ha   = sqlite3.connect(HA_DB); ha.row_factory = sqlite3.Row
    lm   = sqlite3.connect(LM_DB); lm.row_factory = sqlite3.Row

    # Get vehicle_id (must already exist from poller first run)
    vehicle = lm.execute("SELECT id FROM vehicles LIMIT 1").fetchone()
    if not vehicle:
        print("ERROR: No vehicle in LeapMotor Mate DB. Run the poller first.")
        sys.exit(1)
    vehicle_id = vehicle["id"]

    ha_trips = ha.execute("SELECT * FROM trips ORDER BY id").fetchall()
    print(f"Found {len(ha_trips)} trips in HA DB")

    # Check for existing data
    existing = lm.execute("SELECT COUNT(*) FROM trips").fetchone()[0]
    if existing:
        print(f"WARNING: {existing} trips already in LM DB — skipping duplicates by started_at")

    existing_starts = {
        r[0] for r in lm.execute("SELECT started_at FROM trips").fetchall()
    }

    imported = skipped = 0
    for t in ha_trips:
        started_at = to_iso(t["start"])
        ended_at   = to_iso(t["end"])

        if started_at in existing_starts:
            skipped += 1
            continue

        duration_min       = parse_duration(t["durata"])
        distance_km        = float(t["km"] or 0)
        efficiency         = float(t["cons"]) if t["cons"] else None
        # HA stores kWh directly — recalculate efficiency if missing
        if not efficiency and distance_km > 0 and t["kwh"]:
            efficiency = round(float(t["kwh"]) / distance_km * 100, 2)

        lm.execute(
            """INSERT INTO trips
               (vehicle_id, started_at, ended_at,
                start_odometer_km, end_odometer_km, distance_km,
                start_soc, end_soc,
                duration_min, efficiency_kwh_100km)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                vehicle_id, started_at, ended_at,
                float(t["km_start"] or 0), float(t["km_end"] or 0), distance_km,
                float(t["soc_start"] or 0), float(t["soc_end"] or 0),
                duration_min, efficiency,
            ),
        )
        imported += 1

    lm.commit()
    print(f"Imported: {imported}  |  Skipped (duplicates): {skipped}")

    # Summary
    count = lm.execute("SELECT COUNT(*) FROM trips").fetchone()[0]
    total_km = lm.execute("SELECT SUM(distance_km) FROM trips WHERE ended_at IS NOT NULL").fetchone()[0]
    print(f"Total in DB: {count} trips, {round(total_km or 0, 1)} km")

    ha.close(); lm.close()


if __name__ == "__main__":
    main()
