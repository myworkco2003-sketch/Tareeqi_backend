
import sqlite3
from pathlib import Path

from django.http import HttpResponse, Http404
from django.views.decorators.http import require_GET
from django.conf import settings
from django.views.decorators.cache import cache_control


MBTILES_PATH = Path(
    r"D:\v1_mobile_dleel\assets\damascus.mbtiles"
)
FONTS_PATH = Path(r"D:\tareeq\assets\fonts\Noto Sans Bold")


@require_GET
@cache_control(public=True, max_age=86400)
def get_damascus_tile(request, z, x, y):
    if not MBTILES_PATH.is_file():
        raise Http404("MBTiles file not found")

    tms_y = (2 ** z) - 1 - y

    try:
        with sqlite3.connect(
            f"file:{MBTILES_PATH.as_posix()}?mode=ro",
            uri=True,
            timeout=5,
        ) as db:
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
    except sqlite3.Error:
        raise Http404("Unable to read map tile")

    if row is None:
        raise Http404("Tile not found")

    response = HttpResponse(
        row[0],
        content_type="application/x-protobuf",
    )
    response["Content-Encoding"] = "gzip"
    return response


@require_GET
@cache_control(public=True, max_age=86400)
def get_font(request, fontstack, font_range):
    if fontstack != "Noto Sans Bold":
        raise Http404("Font not found")

    font_file = FONTS_PATH / f"{font_range}.pbf"

    if not font_file.is_file():
        raise Http404("Glyph range not found")

    return HttpResponse(
        font_file.read_bytes(),
        content_type="application/x-protobuf",
    )
