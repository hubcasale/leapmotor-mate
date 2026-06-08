"""HOME charges on a wallbox are billed on the real AC energy the wallbox delivered (what you pay),
not just the DC energy into the battery. Other charges (no ac_kwh) keep DC billing."""
import db_reader
import main


def _patch_flat(monkeypatch, home_price=0.25):
    monkeypatch.setattr(db_reader, "get_cost_config",
                        lambda: {"mode": "flat", "method": "split", "bands": []})
    monkeypatch.setattr(db_reader, "get_charge_prices", lambda: {"price_home_kwh": home_price})


CHARGE = {"location_type": "HOME", "energy_added_kwh": 8.0,
          "started_at": "2026-06-02T16:48:39+00:00", "ended_at": "2026-06-02T21:18:36+00:00"}


def test_cost_uses_ac_kwh_when_given(monkeypatch):
    _patch_flat(monkeypatch)
    assert db_reader.compute_cost(CHARGE) == 2.0                  # DC: 8 kWh × 0.25
    assert db_reader.compute_cost(CHARGE, ac_kwh=10.0) == 2.5     # AC: 10 kWh × 0.25 (losses billed)


def test_cost_falls_back_to_dc_without_ac(monkeypatch):
    _patch_flat(monkeypatch)
    assert db_reader.compute_cost(CHARGE, ac_kwh=None) == 2.0     # no wallbox data → DC
    assert db_reader.compute_cost(CHARGE, ac_kwh=0) == 2.0        # 0/invalid → DC
    assert db_reader.compute_cost(CHARGE, ac_kwh=-1) == 2.0       # guard against bad values


# ── _session_energy plausibility guard (GitHub #24 / FB: 10889 kWh AC, 0.1% efficiency) ──
def _patch_wallbox(monkeypatch, hist):
    """Drive _session_energy through its AC branch with a fake HA wallbox power history."""
    monkeypatch.setattr(main.ha_client, "epoch", lambda t: float(t))
    monkeypatch.setattr(main.ha_client, "get_mapping", lambda: {"power": "sensor.wb"})
    monkeypatch.setattr(main.ha_client, "is_configured", lambda: True)
    monkeypatch.setattr(main.ha_client, "get_history", lambda e, a, b: hist)
    monkeypatch.setattr(main.db_reader, "get_setting",
                        lambda k, d=None: "1" if k == "wallbox_enabled" else d)


def _dense_curve(kw, minutes=60, step_s=60):
    """A realistically-sampled charge curve (a point every step_s) at constant kW. Real curves
    sample every poll (~30-60s); 2-point curves >15min apart would now be dropped by the gap guard."""
    n = minutes * 60 // step_s
    return {"times": [str(i * step_s) for i in range(n + 1)], "power": [float(kw)] * (n + 1)}


def _hold(val):
    """A 2-point HA history that step-holds `val` across the whole window."""
    return [(0.0, float(val)), (1e12, float(val))]


# DC curve: 5 kW for 1h → 5 kWh into the battery.
CURVE = _dense_curve(5.0)


def test_session_energy_discards_implausible_ac(monkeypatch):
    # AC "power" is actually a cumulative kWh meter reading ~10880 → integrates to ~10880 kWh.
    _patch_wallbox(monkeypatch, _hold(10880.0))
    out = main._session_energy(CURVE)
    assert out["dc_kwh"] == 5.0
    assert out["ac_kwh"] is None      # > 2×DC → physically impossible → discarded
    assert out["eff"] is None


def test_session_energy_keeps_plausible_ac(monkeypatch):
    # AC ~5.9 kW for 1h → 5.9 kWh, ≈85% efficiency → a normal charge, kept untouched.
    _patch_wallbox(monkeypatch, _hold(5.9))
    out = main._session_energy(CURVE)
    assert out["dc_kwh"] == 5.0
    assert out["ac_kwh"] == 5.9
    assert out["eff"] == 84.7


def test_session_energy_discards_ac_when_dc_zero(monkeypatch):
    # Degenerate: DC integrates to exactly 0 (e.g. all-zero V·I) but a mis-mapped AC reads huge.
    # The guard must NOT let the unvalidatable AC survive (would bill HOME on it / show 0% eff).
    _patch_wallbox(monkeypatch, _hold(10880.0))
    out = main._session_energy(_dense_curve(0.0))
    assert out["dc_kwh"] == 0.0
    assert out["ac_kwh"] is None      # no positive DC to validate against → discarded
    assert out["eff"] is None


def test_auto_confirm_home_charges(monkeypatch):
    monkeypatch.setattr(db_reader, "get_setting",
                        lambda k, d=None: "1" if k == "wallbox_enabled" else d)
    monkeypatch.setattr(main.ha_client, "is_configured", lambda: True)
    monkeypatch.setattr(main.ha_client, "get_mapping", lambda: {"power": "sensor.wb"})
    monkeypatch.setattr(main.ha_client, "epoch", lambda t: float(t))
    monkeypatch.setattr(main.ha_client, "get_history", lambda e, a, b: _hold(5.9))
    monkeypatch.setattr(db_reader, "get_unconfirmed_charge_ids", lambda limit=None: [1])
    monkeypatch.setattr(db_reader, "get_charge_power_curve", lambda charge_id: CURVE)
    updated = []
    def fake_update(charge_id, location_type, ac_kwh=None):
        updated.append((charge_id, location_type, ac_kwh))
        return {"id": charge_id, "location_type": location_type}
    monkeypatch.setattr(db_reader, "update_charge_type", fake_update)

    confirmed = main._wallbox_auto_confirm_home_charges()
    assert confirmed == 1
    assert updated == [(1, "HOME", 5.9)]


def test_integrate_kwh_skips_long_gap():
    # 5 kW held across a 15-min step is counted; held across a 2-hour gap is a phantom → skipped.
    assert round(main._integrate_kwh([(0.0, 5.0), (900.0, 5.0)]), 3) == 1.25   # 0.25h → 1.25 kWh
    assert main._integrate_kwh([(0.0, 5.0), (7200.0, 5.0)]) == 0.0             # 2h gap → dropped
