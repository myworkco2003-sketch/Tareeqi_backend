import sqlite3
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, Response

router = APIRouter()

MBTILES_PATH = Path(r"D:\tareeq\assets\damascus.mbtiles")

@router.get("/tiles/damascus/{z}/{x}/{y}")
def get_damascus_tile(z: int, x: int, y: int):
    if not MBTILES_PATH.exists():
        raise HTTPException(status_code=404, detail="MBTiles file not found")

    tms_y = (2 ** z) - 1 - y

    db = sqlite3.connect(MBTILES_PATH)

    try:
        row = db.execute(
            """
            SELECT images.tile_data
            FROM map
            JOIN images ON images.tile_id = map.tile_id
            WHERE map.zoom_level = ?
              AND map.tile_column = ?
              AND map.tile_row = ?
            """,
            (z, x, tms_y),
        ).fetchone()
    finally:
        db.close()

    if row is None:
        raise HTTPException(status_code=404, detail="Tile not found")

    return Response(
        content=row[0],
        media_type="application/x-protobuf",
        headers={
            "Content-Encoding": "gzip",
        },
    )

FONTS_PATH = Path(r"D:\tareeq\assets\fonts\Noto Sans Bold")


@router.get("/fonts/{fontstack}/{font_range}.pbf")
def get_font(fontstack: str, font_range: str):
    if fontstack != "Noto Sans Bold":
        raise HTTPException(status_code=404, detail="Font not found")

    font_file = FONTS_PATH / f"{font_range}.pbf"

    if not font_file.exists():
        raise HTTPException(status_code=404, detail="Glyph range not found")

    return FileResponse(
        font_file,
        media_type="application/x-protobuf",
    )   