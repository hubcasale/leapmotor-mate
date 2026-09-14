"""auto_detect_charge_type_from_power(): type a still-unconfirmed charge from its own measured
peak power. Scoped to max_power_kw > charge_dc_min_kw ONLY — it must never assign AC, because a
home wallbox's own power sits inside that same range and stealing it here would remove the only
tagging path an install with no HA wallbox integration has for HOME. Unlike its two HOME-sweep
neighbours in db_reader, it carries no setting of its own — it reads a real measurement, not an
inferred proxy — but it DOES yield to charger_locator's geolocation-based classification when
that's on (web/charger_locator.py:classify_from_station can tell HPC from plain DC, this can't),
see the "yields to geolocation" tests below.

Everything runs on a tmp_path DB (poller schema + db_reader pointed at it) — no settings DB,
CI-safe."""
import db as D
import db_reader


def _setup(tmp_path, monkeypatch):
    pdb = D.Database(str(tmp_path / "t.db"))
    monkeypatch.setattr(db_reader, "DB_PATH", str(tmp_path / "t.db"))
    return pdb


def _charge(pdb, cid, *, max_power_kw, ended="2026-06-02T21:18:36+00:00",
            ctype=None, reconstructed=0, ac=None, lat=None, lon=None, name=None):
    pdb._conn.execute(
        "INSERT INTO charges (id, vehicle_id, started_at, ended_at, start_soc, end_soc,"
        " energy_added_kwh, ac_energy_kwh, max_power_kw, location_type, reconstructed,"
        " latitude, longitude, location_name)"
        " VALUES (?,1,'2026-06-02T16:48:39+00:00',?,40,52,8.0,?,?,?,?,?,?,?)",
        (cid, ended, ac, max_power_kw, ctype, reconstructed, lat, lon, name))
    pdb._conn.commit()


def _row(pdb, cid):
    return pdb._conn.execute("SELECT * FROM charges WHERE id=?", (cid,)).fetchone()


def test_never_assigns_ac(tmp_path, monkeypatch):
    """The whole point of the scope restriction: at or below the DC threshold, a charge is left
    exactly where the badge's own '❓ Unconfirmed' flow can still claim it as HOME."""
    pdb = _setup(tmp_path, monkeypatch)
    _charge(pdb, 1, max_power_kw=7.4)    # typical home wallbox
    _charge(pdb, 2, max_power_kw=11.0)   # exactly at the default threshold
    assert db_reader.auto_detect_charge_type_from_power() == 0
    assert _row(pdb, 1)["location_type"] is None
    assert _row(pdb, 2)["location_type"] is None


def test_assigns_fast_above_the_threshold(tmp_path, monkeypatch):
    pdb = _setup(tmp_path, monkeypatch)
    _charge(pdb, 1, max_power_kw=35.0)
    assert db_reader.auto_detect_charge_type_from_power() == 1
    assert _row(pdb, 1)["location_type"] == "FAST"


def test_never_assigns_hpc_however_high_the_power(tmp_path, monkeypatch):
    """Power is the CAR's own charging curve, not the charger's rating or tariff class — a car on a
    genuine 300 kW HPC charger can still measure well under any threshold depending on where its
    curve sits (SoC, battery temperature). So even a very high reading only ever means DC, never
    HPC — that call stays a plain human judgement on the badge, exactly as it always has."""
    pdb = _setup(tmp_path, monkeypatch)
    _charge(pdb, 1, max_power_kw=150.0)
    assert db_reader.auto_detect_charge_type_from_power() == 1
    assert _row(pdb, 1)["location_type"] == "FAST"


def test_threshold_is_user_configurable(tmp_path, monkeypatch):
    pdb = _setup(tmp_path, monkeypatch)
    db_reader.set_setting("charge_dc_min_kw", "22")
    _charge(pdb, 1, max_power_kw=15.0)    # above the default floor, below the raised one
    assert db_reader.auto_detect_charge_type_from_power() == 0
    assert _row(pdb, 1)["location_type"] is None


def test_already_typed_charges_are_left_alone(tmp_path, monkeypatch):
    pdb = _setup(tmp_path, monkeypatch)
    _charge(pdb, 1, max_power_kw=150.0, ctype="HOME")
    assert db_reader.auto_detect_charge_type_from_power() == 0
    assert _row(pdb, 1)["location_type"] == "HOME"


def test_an_in_progress_charge_is_not_typed_mid_session(tmp_path, monkeypatch):
    """max_power_kw is still climbing while the session runs — never tag it from a number that
    hasn't settled yet."""
    pdb = _setup(tmp_path, monkeypatch)
    _charge(pdb, 1, max_power_kw=150.0, ended=None)
    assert db_reader.auto_detect_charge_type_from_power() == 0
    assert _row(pdb, 1)["location_type"] is None


def test_a_reconstructed_charge_is_left_alone(tmp_path, monkeypatch):
    pdb = _setup(tmp_path, monkeypatch)
    _charge(pdb, 1, max_power_kw=150.0, reconstructed=1)
    assert db_reader.auto_detect_charge_type_from_power() == 0
    assert _row(pdb, 1)["location_type"] is None


def test_it_goes_through_update_charge_type_so_it_prices_too(tmp_path, monkeypatch):
    """Same guarantee as its HOME siblings: the sweep is not a second implementation of pricing —
    it hits the one function everything else does."""
    pdb = _setup(tmp_path, monkeypatch)
    db_reader.set_setting("price_fast_kwh", "0.60")
    _charge(pdb, 1, max_power_kw=35.0)
    db_reader.auto_detect_charge_type_from_power()
    row = _row(pdb, 1)
    assert row["location_type"] == "FAST"
    assert row["cost"] == 4.8   # 8 kWh (energy_added_kwh) × 0.60


def test_a_home_eligible_charge_is_claimed_by_the_home_sweep_first(tmp_path, monkeypatch):
    """Ordering, as wired in _ctx(): auto_confirm_home_charges runs BEFORE this one, so a charge
    with real wallbox energy never reaches the power-based sweep at all — even though its power
    would otherwise clear the DC threshold."""
    pdb = _setup(tmp_path, monkeypatch)
    db_reader.set_setting("wallbox_auto_home", "1")
    db_reader.set_setting("price_home_kwh", "0.25")
    _charge(pdb, 1, max_power_kw=35.0, ac=10.0)   # both eligible for HOME and above the DC floor
    assert db_reader.auto_confirm_home_charges() == 1
    assert db_reader.auto_detect_charge_type_from_power() == 0   # nothing left for it to see
    assert _row(pdb, 1)["location_type"] == "HOME"


# ── yields to geolocation when charger_locator is on (fork-only) ──────────────
# Without this, the synchronous, every-page-render car-curve sweep would almost always
# claim a DC-eligible charge as flat FAST within seconds of it ending — long before the
# async, TTL-throttled geolocation sweep ever got a chance to try for a confident HPC
# answer instead. location_name IS NOT NULL (even '' — "looked up, nothing") is the
# sentinel the geolocation sweep already writes the moment it has looked at a charge;
# reused here instead of a new column.

def test_waits_for_geolocation_when_charger_locator_is_on(tmp_path, monkeypatch):
    pdb = _setup(tmp_path, monkeypatch)
    db_reader.set_setting("charger_locator", "1")
    _charge(pdb, 1, max_power_kw=150.0, lat=45.0, lon=9.0)   # geo-eligible, not yet swept
    assert db_reader.auto_detect_charge_type_from_power() == 0
    assert _row(pdb, 1)["location_type"] is None


def test_claims_it_once_geolocation_has_had_its_say(tmp_path, monkeypatch):
    """Whether or not geolocation actually found a name — an empty-string sentinel
    (looked up, nothing there) unblocks this sweep exactly the same as a real name."""
    pdb = _setup(tmp_path, monkeypatch)
    db_reader.set_setting("charger_locator", "1")
    _charge(pdb, 1, max_power_kw=150.0, lat=45.0, lon=9.0, name="")   # geo already looked, found nothing
    assert db_reader.auto_detect_charge_type_from_power() == 1
    assert _row(pdb, 1)["location_type"] == "FAST"


def test_does_not_wait_when_charger_locator_is_off(tmp_path, monkeypatch):
    pdb = _setup(tmp_path, monkeypatch)
    _charge(pdb, 1, max_power_kw=150.0, lat=45.0, lon=9.0)   # charger_locator off (default)
    assert db_reader.auto_detect_charge_type_from_power() == 1
    assert _row(pdb, 1)["location_type"] == "FAST"


def test_does_not_wait_for_a_charge_with_no_gps_fix(tmp_path, monkeypatch):
    """Geolocation can never resolve a charge with no GPS fix regardless of the setting —
    so this sweep must not stall on one waiting for a lookup that will never happen."""
    pdb = _setup(tmp_path, monkeypatch)
    db_reader.set_setting("charger_locator", "1")
    _charge(pdb, 1, max_power_kw=150.0, lat=None, lon=None)
    assert db_reader.auto_detect_charge_type_from_power() == 1
    assert _row(pdb, 1)["location_type"] == "FAST"
