"""Render a small cluster-map PNG with one seat highlighted.

Designed to look clean on a Discord embed: dark background that matches
discord's dark theme, blurple seats, red highlight, white labels.

The image is centered on the target seat so the visual is always readable
regardless of how big the actual cluster is — we render a window of N
rows × N cols around the target.
"""

from __future__ import annotations

import io

from PIL import Image, ImageDraw, ImageFont

# Discord dark-theme palette
BG = (47, 49, 54)            # #2f3136
GRID = (54, 57, 63)           # #36393f
SEAT = (88, 101, 242)         # blurple #5865f2
SEAT_OUTLINE = (78, 84, 168)
TARGET = (237, 66, 69)        # red #ed4245
TARGET_OUTLINE = (200, 50, 53)
LABEL = (220, 221, 222)       # off-white

CELL = 32
GAP = 6
MARGIN = 36
WINDOW = 7  # window size: WINDOW × WINDOW cells centered on the target


def _load_font(size: int) -> ImageFont.ImageFont:
    """Try a few common font paths; fall back to PIL's default bitmap."""
    for path in (
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ):
        try:
            return ImageFont.truetype(path, size=size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


def render_cluster_map(
    cluster: int,
    row: int,
    seat: int,
    floor: str | None = None,
    window: int = WINDOW,
) -> bytes:
    """Render an N×N seat grid centered on (row, seat). Returns PNG bytes.

    The grid axis labels are real row/seat numbers (not 1..N), so the user
    can read off the absolute coordinates even though the window is local.
    """
    half = window // 2
    row_start = max(1, row - half)
    seat_start = max(1, seat - half)

    width = MARGIN * 2 + window * CELL + (window - 1) * GAP + 30  # extra for row labels
    height = MARGIN * 2 + window * CELL + (window - 1) * GAP + 40  # extra for header

    img = Image.new("RGB", (width, height), BG)
    draw = ImageDraw.Draw(img)

    title_font = _load_font(16)
    label_font = _load_font(11)

    # Header
    floor_part = f" · {floor}" if floor else ""
    title = f"Cluster {cluster}{floor_part}"
    draw.text((MARGIN, 10), title, font=title_font, fill=LABEL)

    grid_left = MARGIN + 28  # leave room for row labels on the left
    grid_top = MARGIN + 8

    # Column (seat) labels along the top
    for c in range(window):
        seat_num = seat_start + c
        x = grid_left + c * (CELL + GAP)
        draw.text(
            (x + CELL // 2 - 8, grid_top - 16),
            f"P{seat_num}",
            font=label_font,
            fill=LABEL,
        )

    # Row labels + cells
    for r in range(window):
        row_num = row_start + r
        y = grid_top + r * (CELL + GAP)
        draw.text(
            (MARGIN - 4, y + CELL // 2 - 6),
            f"R{row_num}",
            font=label_font,
            fill=LABEL,
        )
        for c in range(window):
            seat_num = seat_start + c
            x = grid_left + c * (CELL + GAP)
            is_target = row_num == row and seat_num == seat
            if is_target:
                fill, outline = TARGET, TARGET_OUTLINE
            else:
                fill, outline = SEAT, SEAT_OUTLINE
            draw.rounded_rectangle(
                (x, y, x + CELL, y + CELL),
                radius=6,
                fill=fill,
                outline=outline,
                width=1,
            )

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
