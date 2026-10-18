from __future__ import annotations

from datetime import datetime, timezone
from math import asin, cos, radians, sin, sqrt

from fastapi import HTTPException


def distance_m(a: dict, b: dict) -> float:
    """Great-circle distance between two GPS fixes in meters."""
    lat1, lat2 = radians(a["latitude"]), radians(b["latitude"])
    dlat = lat2 - lat1
    dlon = radians(b["longitude"] - a["longitude"])
    h = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 6_371_000 * 2 * asin(sqrt(min(1.0, h)))


def validate_point_order(previous: dict | None, point: dict) -> None:
    now = datetime.now(timezone.utc)
    stamp = point["client_timestamp"]
    if stamp.tzinfo is None:
        raise HTTPException(422, "Location timestamps must include a timezone.")
    if (now - stamp.astimezone(timezone.utc)).total_seconds() > 43200:
        raise HTTPException(422, "Location update is older than twelve hours; older offline points are not accepted.")
    if (stamp.astimezone(timezone.utc) - now).total_seconds() > 30:
        raise HTTPException(422, "Location timestamp is in the future.")
    if previous:
        if point["sequence_number"] <= previous["sequence_number"]:
            raise HTTPException(409, "Duplicate or out-of-order location sequence.")
        if stamp <= previous["client_timestamp"]:
            raise HTTPException(409, "Location timestamps must increase.")
        elapsed = (stamp - previous["client_timestamp"]).total_seconds()
        distance = distance_m(previous, point)
        # Reject obviously impossible speeds while allowing poor GPS fixes; raw
        # accepted points remain stored and the frontend marks weak accuracy.
        if elapsed > 0 and distance / elapsed > 90:
            raise HTTPException(422, "Location jump exceeds the safe movement limit.")

