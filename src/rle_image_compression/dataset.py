from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

from pathlib import Path

from PIL import Image

from .image_generator import generate_dataset_sources


Matrix = List[List[int]]


@dataclass
class VariantSpec:
    pixels: Matrix
    bpp: int
    palette: List[Tuple[int, int, int]]


def _clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def _matrix_from_image(image: Image.Image) -> Matrix:
    width, height = image.size
    flat = list(image.getdata())
    return [flat[row * width : (row + 1) * width] for row in range(height)]


def _extract_palette_rgb(p_image: Image.Image, used_colors: int, total_size: int = 256) -> List[Tuple[int, int, int]]:
    raw = p_image.getpalette() or []
    palette: List[Tuple[int, int, int]] = []
    for i in range(used_colors):
        base = i * 3
        r = raw[base] if base < len(raw) else 0
        g = raw[base + 1] if base + 1 < len(raw) else 0
        b = raw[base + 2] if base + 2 < len(raw) else 0
        palette.append((r, g, b))

    # BMP 8-bit indexed expects 256 palette slots in this project codec.
    while len(palette) < total_size:
        palette.append((0, 0, 0))
    return palette[:total_size]

def quantize_bw(image: Matrix) -> Matrix:
    return [[1 if value >= 128 else 0 for value in row] for row in image]


def quantize_gray4(image: Matrix) -> Matrix:
    return [[value // 16 for value in row] for row in image]


def quantize_pal8(image: Matrix) -> Matrix:
    return [[_clamp(value, 0, 255) for value in row] for row in image]


def get_palettes() -> Dict[str, List[Tuple[int, int, int]]]:
    bw_palette = [(0, 0, 0), (255, 255, 255)]
    gray4_palette = [(i * 17, i * 17, i * 17) for i in range(16)]
    pal8_palette = [(i, i, i) for i in range(256)]
    return {
        "bw_1bit": bw_palette,
        "gray_4bit": gray4_palette,
        "palette_8bit": pal8_palette,
    }


def build_rocket_variants(project_root: Path) -> Tuple[str, Dict[str, VariantSpec]]:
    generated_sources = generate_dataset_sources(project_root, size=512)
    source_name = "rocket_orbit_launch_512"
    _ = generated_sources[source_name]
    source_path = project_root / "images" / "generated_sources" / f"{source_name}.png"
    base_image = Image.open(source_path).convert("RGB")

    return build_variants_for_image(source_name, base_image)


def build_variants_for_image(source_name: str, base_image_rgb: Image.Image) -> Tuple[str, Dict[str, VariantSpec]]:
    gray_l = base_image_rgb.convert("L")

    # 1-bit B&W: binary thresholded image, indexed palette with 2 colors.
    bw_pixels = quantize_bw(_matrix_from_image(gray_l))
    bw_palette = [(0, 0, 0), (255, 255, 255)]

    # True 4-bit grayscale: 16 quantization levels, stored as 4-bit indexed BMP.
    gray4_pixels = quantize_gray4(_matrix_from_image(gray_l))
    gray4_palette = [(i * 17, i * 17, i * 17) for i in range(16)]

    # Color table 8-bit: from original RGB with adaptive 256-color palette.
    color8_p = base_image_rgb.quantize(colors=256, method=Image.Quantize.MEDIANCUT)
    color8_pixels = _matrix_from_image(color8_p)
    color8_palette = _extract_palette_rgb(color8_p, used_colors=256, total_size=256)

    variants: Dict[str, VariantSpec] = {
        "bw_1bit": VariantSpec(pixels=bw_pixels, bpp=1, palette=bw_palette),
        "gray_4bit": VariantSpec(pixels=gray4_pixels, bpp=4, palette=gray4_palette),
        "palette_8bit": VariantSpec(pixels=color8_pixels, bpp=8, palette=color8_palette),
    }

    return source_name, variants


def load_external_source_with_padding(
    image_path: Path,
    output_preview_path: Path,
    size: int = 512,
    bg_value: int = 18,
) -> Tuple[str, Image.Image]:
    # Keep color for preview output; convert to grayscale only for downstream quantization.
    image = Image.open(image_path).convert("RGBA")
    src_w, src_h = image.size

    if src_w == 0 or src_h == 0:
        raise ValueError(f"Invalid image dimensions for {image_path}")

    scale = min(size / src_w, size / src_h)
    new_w = max(1, int(round(src_w * scale)))
    new_h = max(1, int(round(src_h * scale)))

    resized = image.resize((new_w, new_h), Image.Resampling.BICUBIC)
    canvas = Image.new("RGBA", (size, size), color=(bg_value, bg_value, bg_value, 255))
    offset_x = (size - new_w) // 2
    offset_y = (size - new_h) // 2
    canvas.paste(resized, (offset_x, offset_y))

    output_preview_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(output_preview_path)

    source_name = f"external_{image_path.stem}_512"
    return source_name, canvas.convert("RGB")
