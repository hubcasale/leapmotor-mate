"""_parse_vehicle_status window mapping (#62, T03 windows).

A window is open if its open/closed flag (1693-1696) OR — only where it's a trusted sensor for this
car — its position % (3727/3728/1879/1880) is non-zero. The two sources are model-specific: the B10
drives the flags and its position % is a DEAD/garbage sensor (marked `windows_pct` broken in its
capability profile), while the T03 leaves the flags at 0 and reports only the live position %.
Reading the flags alone showed the T03's open windows as always "closed"; blindly OR-ing the % made
the B10's dead %-sensor false-positive every window — so the % fallback is gated on the profile.

Values below are from gody01's real T03 captures (bundle-3 closed / bundle-4 opened ~20% via the
official app). Needs web.main (fastapi) → skipped in the minimal CI test env, like the other
main-based tests."""
import pytest

pytest.importorskip("fastapi", reason="web.main needs fastapi (absent in the minimal CI test env)")

import main


def _windows(sig, vin, monkeypatch, *, pct_trusted):
    # windows_pct trusted (T03) vs broken/ignored (B10); other features default to shown.
    monkeypatch.setattr(main.capability_profile, "is_shown",
                        lambda v, feat, *a, **k: pct_trusted if feat == "windows_pct" else True)
    return main._parse_vehicle_status(sig, vin)["windows"]


def test_t03_open_windows_read_from_percent(monkeypatch):
    # flags stay false but the position % is 20 → all four windows must read as OPEN.
    sig = {"1693": False, "1694": False, "1695": False, "1696": False,
           "3727": 20, "3728": 20, "1879": 20, "1880": 20}
    w = _windows(sig, "T03VIN", monkeypatch, pct_trusted=True)
    assert (w["fl"], w["fr"], w["rl"], w["rr"]) == (True, True, True, True)


def test_t03_closed_windows(monkeypatch):
    sig = {"1693": False, "1694": False, "1695": False, "1696": False,
           "3727": 0, "3728": 0, "1879": 0, "1880": 0}
    w = _windows(sig, "T03VIN", monkeypatch, pct_trusted=True)
    assert (w["fl"], w["fr"], w["rl"], w["rr"]) == (False, False, False, False)


def test_b10_dead_percent_does_not_false_positive(monkeypatch):
    # The exact regression (#62): on the B10 `windows_pct` is broken, so the dead sensor's garbage
    # (here 50) MUST be ignored — with the flags at 0 the windows read CLOSED, not open.
    sig = {"1693": 0, "1694": 0, "1695": 0, "1696": 0,
           "3727": 50, "3728": 50, "1879": 50, "1880": 50}
    w = _windows(sig, "B10VIN", monkeypatch, pct_trusted=False)
    assert (w["fl"], w["fr"], w["rl"], w["rr"]) == (False, False, False, False)


def test_b10_open_window_read_from_flag(monkeypatch):
    # B10: the open/closed flag drives it (% ignored), per-window mapping respected (only FL).
    sig = {"1693": 1, "1694": 0, "1695": 0, "1696": 0}
    w = _windows(sig, "B10VIN", monkeypatch, pct_trusted=False)
    assert (w["fl"], w["fr"], w["rl"], w["rr"]) == (True, False, False, False)


def test_windows_none_when_unreported(monkeypatch):
    # car asleep / no window signals at all → None (unknown), not a false "closed".
    w = _windows({}, "VIN", monkeypatch, pct_trusted=True)
    assert w["fl"] is None and w["sunshade"] is None
