
import sqlite3

from django.http import HttpResponse, Http404
from django.views.decorators.http import require_GET
from django.conf import settings
from django.views.decorators.cache import cache_control


@require_GET
@cache_control(public=True, max_age=86400)
def get_damascus_tile(request, z, x, y):
    if not settings.MBTILES_PATH.is_file():
        raise Http404("MBTiles file not found")

    tms_y = (2 ** z) - 1 - y

    try:
        with sqlite3.connect(
            f"file:{settings.MBTILES_PATH.as_posix()}?mode=ro",
            uri=True,
            timeout=5,
        ) as db:
            row = db.execute(
                """
                SELECT tile_data
                FROM tiles
                WHERE zoom_level = ?
                  AND tile_column = ?
                  AND tile_row = ?
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
    if fontstack != "Klokantech Noto Sans Regular":
        raise Http404("Font not found")

    font_file = settings.FONT_PATH / fontstack / f"{font_range}.pbf"

    if not font_file.is_file():
        raise Http404("Glyph range not found")

    return HttpResponse(
        font_file.read_bytes(),
        content_type="application/x-protobuf",
    )
