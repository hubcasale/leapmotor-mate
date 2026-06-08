"""Charging station lookup / operator detection.

Uses OpenStreetMap's Overpass API to find nearby amenity=charging_station POIs.
This is best-effort: only when the nearby location is unambiguous is the station
name/operator filled automatically. When multiple distinct stations are found
nearby, the UI can ask the user to confirm it manually.
"""
import json
import math
import re
import urllib.parse
import urllib.request

_UA = "LeapMotorMate/1.0 (https://github.com/ProtossBlaster/leapmotor-mate)"
_OVERPASS_URL = "https://overpass-api.de/api/interpreter"
_DEFAULT_RADIUS_M = 40


def _get(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(max(0, a)))


def _parse_kw(value: str | None) -> float | None:
    if not value:
        return None
    try:
        v = re.sub(r"[^\d.]+", "", str(value))
        return float(v) if v else None
    except Exception:
        return None


def _candidate(el: dict, lat: float, lon: float) -> dict:
    tags = el.get("tags", {}) or {}
    name = tags.get("name")
    operator = tags.get("operator") or tags.get("brand") or tags.get("network")
    if operator:
        operator = operator.strip()
    if name:
        name = name.strip()
    maxpower_kw = _parse_kw(tags.get("maxpower") or tags.get("capacity"))
    if el.get("type") in ("way", "relation"):
        center = el.get("center", {}) or {}
        cand_lat = center.get("lat")
        cand_lon = center.get("lon")
    else:
        cand_lat = el.get("lat")
        cand_lon = el.get("lon")
    distance_m = None
    if cand_lat is not None and cand_lon is not None:
        distance_m = round(_haversine_km(lat, lon, cand_lat, cand_lon) * 1000, 1)
    return {
        "id": f"{el.get('type')}/{el.get('id')}",
        "name": name,
        "operator": operator,
        "maxpower_kw": maxpower_kw,
        "distance_m": distance_m,
        "tags": tags,
    }


def query_charging_stations(lat: float, lon: float, radius_m: int = _DEFAULT_RADIUS_M) -> list[dict]:
    query = (
        f"[out:json][timeout:15];"
        f"(node[\"amenity\"=\"charging_station\"](around:{radius_m},{lat},{lon});"
        f"way[\"amenity\"=\"charging_station\"](around:{radius_m},{lat},{lon});"
        f"relation[\"amenity\"=\"charging_station\"](around:{radius_m},{lat},{lon});"
        ");out center tags;"
    )
    url = _OVERPASS_URL + "?data=" + urllib.parse.quote(query, safe="")
    resp = _get(url)
    elements = resp.get("elements", [])
    return [_candidate(el, lat, lon) for el in elements if el.get("id") is not None]


def guess_station(lat: float, lon: float, max_power_kw: float | None = None, radius_m: int = _DEFAULT_RADIUS_M) -> dict | None:
    if lat is None or lon is None:
        return None
    candidates = [c for c in query_charging_stations(lat, lon, radius_m) if c.get("distance_m") is not None]
    if not candidates:
        return None
    candidates.sort(key=lambda c: c["distance_m"] or 0)
    groups: dict[tuple[str, str], list[dict]] = {}
    for c in candidates:
        key = ((c["operator"] or "").lower().strip(), (c["name"] or "").lower().strip())
        groups.setdefault(key, []).append(c)
    if len(groups) == 1:
        cand = next(iter(groups.values()))[0]
        return {
            "station_name": cand["name"] or cand["operator"] or "Charging station",
            "station_operator": cand["operator"] or cand["name"] or "Charging station",
            "ambiguous": False,
            "candidates": candidates,
        }
    operators = {c["operator"] for c in candidates if c["operator"]}
    if len(operators) == 1:
        operator = next(iter(operators))
        cand = candidates[0]
        return {
            "station_name": cand["name"] or operator,
            "station_operator": operator,
            "ambiguous": False,
            "candidates": candidates,
        }
    return {"ambiguous": True, "candidates": candidates}
