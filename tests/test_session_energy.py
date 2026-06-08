"""web.main._session_energy — AC-vs-DC energy comparison + the plausibility guard (GitHub #24 / FB report:
10889 kWh AC at ~0.1% efficiency). Also covers _integrate_kwh's >15min gap guard.

These need web.main, which imports fastapi. CI's minimal test env doesn't install it, so importorskip
skips this module cleanly there — the tests run locally and in the Docker image (full app deps), and the
behaviour is also covered end-to-end by the repro harness."""
import pytest

pytest.importorskip("fastapi", reason="web.main needs fastapi (absent in the minimal CI test env)")
import main


def _patch_wallbox(monkeypatch, hist):
    """Drive _session_energy through its AC branch with a fake HA wallbox power history."""
    monkeypatch.setattr(main.ha_client, "epoch", lambda t: float(t))
    monkeypatch.setattr(main.ha_client, "get_mapping", lambda: {"power": "sensor.wb"})
    monkeypatch.setattr(main.ha_client, "is_configured", lambda: True)
    monkeypatch.setattr(main.ha_client, "get_history", lambda e, a, b: hist)
    monkeypatch.setattr(main.db_reader, "get_setting",
                        lambda k, d=None: "1" if k == "wallbox_enabled" else d)


def _dense_curve(kw, minutes=60, step_s=60):
    """A realistically-sampled charge curve (a point every step_s) at constant kW. Real curves sample
    every poll (~30-60s); 2-point curves >15min apart would now be dropped by the gap guard."""
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


def test_integrate_kwh_skips_long_gap():
    # 5 kW held across a 15-min step is counted; held across a 2-hour gap is a phantom → skipped.
    assert round(main._integrate_kwh([(0.0, 5.0), (900.0, 5.0)]), 3) == 1.25   # 0.25h → 1.25 kWh
    assert main._integrate_kwh([(0.0, 5.0), (7200.0, 5.0)]) == 0.0             # 2h gap → dropped
