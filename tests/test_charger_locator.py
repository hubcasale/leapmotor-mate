import json

from web import charger_locator


def test_guess_station_single_candidate(monkeypatch):
    monkeypatch.setattr(charger_locator, "_get", lambda url: {
        "elements": [
            {
                "type": "node",
                "id": 100,
                "lat": 45.0,
                "lon": 9.0,
                "tags": {
                    "name": "Enel X Fast",
                    "operator": "ENELx",
                    "maxpower": "50 kW",
                },
            }
        ]
    })
    guessed = charger_locator.guess_station(45.0, 9.0, 50.0)
    assert guessed is not None
    assert guessed["ambiguous"] is False
    assert guessed["station_operator"] == "ENELx"
    assert "Enel" in guessed["station_name"]


def test_guess_station_ambiguous(monkeypatch):
    monkeypatch.setattr(charger_locator, "_get", lambda url: {
        "elements": [
            {
                "type": "node",
                "id": 101,
                "lat": 45.0,
                "lon": 9.0,
                "tags": {
                    "name": "Plenitude Charger",
                    "operator": "PLENITUDE",
                },
            },
            {
                "type": "node",
                "id": 102,
                "lat": 45.0,
                "lon": 9.0,
                "tags": {
                    "name": "Enel X Fast",
                    "operator": "ENELx",
                },
            },
        ]
    })
    guessed = charger_locator.guess_station(45.0, 9.0, 50.0)
    assert guessed is not None
    assert guessed["ambiguous"] is True
