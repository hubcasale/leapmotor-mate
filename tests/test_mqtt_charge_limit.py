"""Writable Home Assistant charge-limit (target SoC) over MQTT — GitHub #77.

A `number` platform entity (50–100 %, step 1) that shows the configured charge limit
Mate already reads from the car (charge_limit_percent) AND sets it on tap via
api.set_charge_limit. Covers the discovery config, the command-topic routing, and the
poller-side dispatch (range-validated). Mirrors test_mqtt_trunk_toggle.py (#71).
"""
import json
import types
import importlib.util
import pathlib

import pytest

pytest.importorskip("paho.mqtt.client", reason="poller MQTT bridge needs paho (absent in minimal CI)")
import mqtt as M


class _FakeClient:
    def __init__(self):
        self.published = {}

    def publish(self, topic, payload, retain=False):
        self.published[topic] = payload


def _service(prefix="leapmotor"):
    svc = M.MqttService("broker", 1883, topic_prefix=prefix, get_setting=lambda k, d="": d)
    svc.client = _FakeClient()
    return svc


# ── discovery ──────────────────────────────────────────────────────────────────

def test_discovery_publishes_a_charge_limit_number():
    svc = _service()
    svc.publish_discovery(types.SimpleNamespace(vin="VINTEST"))
    topic = "homeassistant/number/leapmotor_mate_vintest/charge_limit/config"
    assert topic in svc.client.published
    conf = json.loads(svc.client.published[topic])
    assert conf["command_topic"] == "leapmotor/VINTEST/charge_limit/set"
    assert conf["state_topic"] == "leapmotor/VINTEST/charge_limit"
    assert conf["min"] == 50 and conf["max"] == 100 and conf["step"] == 1
    assert conf["unit_of_measurement"] == "%"


def test_charge_limit_number_respects_topic_prefix():
    svc = _service(prefix="myprefix")
    svc.publish_discovery(types.SimpleNamespace(vin="VINTEST"))
    topic = "homeassistant/number/myprefix_mate_vintest/charge_limit/config"
    conf = json.loads(svc.client.published[topic])
    assert conf["command_topic"] == "myprefix/VINTEST/charge_limit/set"
    assert conf["state_topic"] == "myprefix/VINTEST/charge_limit"


# ── command-topic routing (mqtt _on_message) ────────────────────────────────────

def test_set_topic_routes_to_on_command():
    svc = _service()
    seen = []
    svc.on_command = lambda vin, cmd, val: seen.append((vin, cmd, val))
    msg = types.SimpleNamespace(topic="leapmotor/VIN9/charge_limit/set", payload=b"70")
    svc._on_message(None, None, msg)
    assert seen == [("VIN9", "charge_limit", "70")]


# ── poller-side dispatch (poller/main._handle_mqtt_command) ──────────────────────

def _poller_main():
    """Load poller/main.py under its own name (it collides with web/main.py otherwise)."""
    path = pathlib.Path(__file__).parents[1] / "poller" / "main.py"
    spec = importlib.util.spec_from_file_location("poller_main", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _dispatch(value, tmp_path):
    import db as D
    pm = _poller_main()
    api = types.SimpleNamespace(
        calls=[],
        set_charge_limit=lambda vin, pct: api.calls.append(("set_charge_limit", vin, pct)),
    )
    client = types.SimpleNamespace(_api=api)
    service = types.SimpleNamespace(last_climate_on=None,
                                    publish_state=lambda vin, k, v: None)
    db = D.Database(str(tmp_path / "t.db"))
    pm._handle_mqtt_command(client, service, db, "VIN1", "charge_limit", value)
    return api.calls


def test_dispatch_sets_target_soc(tmp_path):
    assert _dispatch("70", tmp_path) == [("set_charge_limit", "VIN1", 70)]


def test_dispatch_accepts_float_string(tmp_path):
    # HA `number` entities may publish "80.0".
    assert _dispatch("80.0", tmp_path) == [("set_charge_limit", "VIN1", 80)]


def test_dispatch_rejects_out_of_range(tmp_path):
    assert _dispatch("120", tmp_path) == []     # above max
    assert _dispatch("10", tmp_path) == []      # below min


def test_dispatch_ignores_garbage(tmp_path):
    assert _dispatch("WOBBLE", tmp_path) == []
