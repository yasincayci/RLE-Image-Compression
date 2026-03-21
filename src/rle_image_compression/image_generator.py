from __future__ import annotations

import random
from pathlib import Path
from typing import Dict, List, Tuple

from PIL import Image, ImageDraw


Matrix = List[List[int]]


def _image_to_matrix(image: Image.Image) -> Matrix:
    width, height = image.size
    flat = list(image.getdata())
    return [flat[row * width : (row + 1) * width] for row in range(height)]


def _draw_medium_rocket_image(width: int = 512, height: int = 512, star_count: int = 180) -> Image.Image:
    image = Image.new("L", (width, height), 18)
    draw = ImageDraw.Draw(image)
    rng = random.Random(42)

    # Soft vertical sky gradient.
    for y in range(height):
        base = int(18 + 20 * (y / height))
        for x in range(width):
            image.putpixel((x, y), base)

    # Big crescent moon.
    mx, my, mr = int(width * 0.79), int(height * 0.18), 74
    draw.ellipse([mx - mr, my - mr, mx + mr, my + mr], fill=188)
    # Overlay with dark disk to form a crescent shape.
    draw.ellipse([mx - mr + 32, my - mr - 6, mx + mr + 36, my + mr - 4], fill=22)

    # Keep only larger stars, remove tiny dot-like stars.
    for _ in range(24):
        sx = rng.randint(0, width - 1)
        sy = rng.randint(0, int(height * 0.62))
        radius = rng.randint(2, 4)
        draw.ellipse([sx - radius, sy - radius, sx + radius, sy + radius], fill=232)

    # Single short apartment row at the bottom.
    base_top = int(height * 0.87)
    draw.rectangle([0, base_top, width, height], fill=24)

    x = 0
    while x < width:
        bw = rng.randint(20, 48)
        bh = rng.randint(14, 52)
        left = x
        right = min(width - 1, x + bw)
        top = max(base_top - bh, int(height * 0.74))
        tone = rng.choice([20, 24, 28, 33, 38])
        draw.rectangle([left, top, right, height], fill=tone)

        # Windows that you liked.
        if bw >= 18:
            for wy in range(top + 4, height - 3, 6):
                drift = ((wy - top) // 6) % 3
                for wx in range(left + 3 + drift, right - 2, 6):
                    if rng.random() < 0.44:
                        draw.rectangle([wx, wy, wx + 1, wy + 1], fill=rng.choice([60, 74, 90, 108]))

        # Slanted roof options.
        roof_mode = rng.random()
        if roof_mode < 0.22:
            peak_x = (left + right) // 2
            peak_y = max(0, top - rng.randint(8, 20))
            draw.polygon([(left, top), (right, top), (peak_x, peak_y)], fill=max(16, tone - 4))
        elif roof_mode < 0.34:
            draw.line([(left, top), (right, max(0, top - rng.randint(3, 10)))], fill=max(14, tone - 6), width=2)

        if rng.random() < 0.38:
            sx = (left + right) // 2
            sh = rng.randint(8, 24)
            draw.line([(sx, top), (sx, max(0, top - sh))], fill=rng.choice([44, 52, 64]), width=1)

        x += bw + rng.randint(2, 8)

    # Light atmospheric haze above apartments.
    for _ in range(700):
        gx = rng.randint(0, width - 1)
        gy = rng.randint(int(height * 0.62), int(height * 0.82))
        image.putpixel((gx, gy), rng.choice([24, 30, 36]))

    # Soft haze layers (blob chains, not hard zigzag lines).
    haze_centers = [
        (int(width * 0.20), int(height * 0.60)),
        (int(width * 0.42), int(height * 0.56)),
        (int(width * 0.63), int(height * 0.59)),
    ]
    for hx, hy in haze_centers:
        for _ in range(18):
            rr = rng.randint(9, 24)
            ox = rng.randint(-70, 70)
            oy = rng.randint(-28, 28)
            draw.ellipse([hx + ox - rr, hy + oy - rr, hx + ox + rr, hy + oy + rr], fill=rng.choice([42, 50, 58]))

    cx, cy = 204, 166
    s = 102
    cos_a = 0.70710678
    sin_a = 0.70710678

    def rot(px: float, py: float) -> Tuple[float, float]:
        return (
            cx + px * cos_a - py * sin_a,
            cy + px * sin_a + py * cos_a,
        )

    flame_outer = [rot(-s // 3, s), rot(s // 3, s), rot(0, s + int(s * 1.9))]
    draw.polygon(flame_outer, fill=212)

    # Exhaust smoke trail with reduced detail.
    smoke_anchors = [
        rot(0, s + int(s * 1.9)),
        rot(-6, s + int(s * 2.2)),
        rot(8, s + int(s * 2.6)),
    ]
    for idx, (sx, sy) in enumerate(smoke_anchors):
        base_r = 10 + idx * 4
        for _ in range(2):
            ox = rng.randint(-base_r // 2, base_r // 2)
            oy = rng.randint(-base_r // 2, base_r // 2)
            rr = rng.randint(max(3, base_r - 5), base_r + 2)
            tone = rng.choice([62, 76, 90, 104])
            draw.ellipse([sx + ox - rr, sy + oy - rr, sx + ox + rr, sy + oy + rr], fill=tone)

    # Diagonal smoke drift with clearer slope to reduce row-major dominance.
    for _ in range(4):
        base_x = rng.randint(32, int(width * 0.42))
        base_y = rng.randint(int(height * 0.42), int(height * 0.76))
        step_dx = rng.randint(14, 22)
        step_dy = rng.randint(9, 16)
        for step in range(5):
            cx_sm = base_x + step * step_dx
            cy_sm = base_y - step * step_dy
            rr = rng.randint(5, 11)
            tone = rng.choice([52, 60, 68, 76])
            draw.ellipse([cx_sm - rr, cy_sm - rr, cx_sm + rr, cy_sm + rr], fill=tone)

    # Removed global speckle grain to avoid small black dots around flame and sky.

    body_pts = [rot(-s // 3, -s), rot(s // 3, -s), rot(s // 3, s), rot(-s // 3, s)]
    nose_pts = [rot(0, -s - int(s * 0.82)), rot(-s // 3, -s), rot(s // 3, -s)]
    fin_l = [rot(-s // 3, s // 2), rot(-s * 2 // 3, s + s // 3), rot(-s // 3, s)]
    fin_r = [rot(s // 3, s // 2), rot(s * 2 // 3, s + s // 3), rot(s // 3, s)]
    nozzle_pts = [rot(-s // 3, s - s // 6), rot(s // 3, s - s // 6), rot(s // 2, s), rot(-s // 2, s)]

    draw.polygon(body_pts, fill=182)
    draw.polygon(nose_pts, fill=212)
    draw.polygon(fin_l, fill=160)
    draw.polygon(fin_r, fill=160)
    draw.polygon(nozzle_pts, fill=141)

    wx, wy = rot(0, -s // 4)
    r = s // 7
    draw.ellipse([wx - r, wy - r, wx + r, wy + r], fill=122)
    draw.ellipse([wx - r // 2, wy - r // 2, wx + r // 2, wy + r // 2], fill=204)

    return image


def generate_dataset_sources(project_root: Path, size: int = 512) -> Dict[str, Matrix]:
    source_dir = project_root / "images" / "generated_sources"
    source_dir.mkdir(parents=True, exist_ok=True)

    for old_png in source_dir.glob("*.png"):
        try:
            old_png.unlink()
        except PermissionError:
            # If a viewer/editor locks the file, continue and overwrite target file names later.
            pass

    medium_img = _draw_medium_rocket_image(size, size, star_count=220)
    medium_path = source_dir / "rocket_orbit_launch_512.png"
    medium_img.save(medium_path)

    return {
        "rocket_orbit_launch_512": _image_to_matrix(medium_img),
    }
