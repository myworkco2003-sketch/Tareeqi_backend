import os

import requests
from fastapi import HTTPException


BROUTER_URL = os.getenv("BROUTER_URL", "http://localhost:17777")
# BROUTER_URL = os.getenv("BROUTER_URL", "https://brouter.de")
BROUTER_PROFILE = os.getenv("BROUTER_PROFILE", "car-eco")


def calculate_route(waypoints: list[tuple[float, float]]) -> dict:
    lonlats = "|".join(f"{lon},{lat}" for lon, lat in waypoints)

    try:
        response = requests.get(
            f"{BROUTER_URL}/brouter",
            params={
                "lonlats": lonlats,
                "profile": BROUTER_PROFILE,
                "alternativeidx": 0,
                "format": "geojson",
            },
            timeout=30,
        )
    except requests.RequestException as error:
        raise HTTPException(
            status_code=502,
            detail=f"تعذر الاتصال بـ BRouter ({BROUTER_URL}): {error}",
        ) from error

    if response.status_code != 200:
        raise HTTPException(
            status_code=400,
            detail=f"BRouter: {response.text.strip()[:300]}",
        )

    try:
        data = response.json()
    except ValueError as error:
        raise HTTPException(status_code=502, detail="BRouter رجّع رد غير مفهوم") from error

    if not data.get("features"):
        raise HTTPException(status_code=400, detail="BRouter ما رجّع مسار")

    return data