from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

from pathlib import Path

import numpy as np
from PIL import Image
from skimage import data


Matrix = List[List[int]]


@dataclass
class VariantSpec:
    pixels: Matrix
    bpp: int
    palette: List[Tuple[int, int, int]]


def _clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def _to_uint8(arr: np.ndarray) -> np.ndarray:
    if arr.dtype == np.uint8:
        return arr
    if np.issubdtype(arr.dtype, np.floating):
        arr = np.clip(arr, 0.0, 1.0) * 255.0
    return np.clip(arr, 0, 255).astype(np.uint8)


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


def compute_block_aligned_size(width: int, height: int, block_size: int = 64) -> Tuple[int, int]:
    if width <= 0 or height <= 0:
        raise ValueError("Invalid image dimensions")
    padded_w = ((width + block_size - 1) // block_size) * block_size
    padded_h = ((height + block_size - 1) // block_size) * block_size
    return padded_w, padded_h


def pad_rgb_to_block_grid(
    image: Image.Image,
    block_size: int = 64,
    bg_value: int = 18,
) -> Tuple[Image.Image, Tuple[int, int]]:
    src_w, src_h = image.size
    if src_w == 0 or src_h == 0:
        raise ValueError("Invalid image dimensions")

    padded_w, padded_h = compute_block_aligned_size(src_w, src_h, block_size=block_size)
    canvas = Image.new("RGB", (padded_w, padded_h), color=(bg_value, bg_value, bg_value))
    # Keep top-left alignment so cropping after decode is deterministic.
    canvas.paste(image, (0, 0))
    return canvas, (padded_w, padded_h)


def load_default_skimage_rocket(
    output_preview_path: Path,
) -> Tuple[str, Image.Image]:
    arr = _to_uint8(data.rocket())
    image = Image.fromarray(arr, mode="RGB")

    output_preview_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_preview_path)
    return "skimage_rocket", image


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
) -> Tuple[str, Image.Image]:
    image = Image.open(image_path).convert("RGBA").convert("RGB")

    output_preview_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_preview_path)

    source_name = image_path.stem
    return source_name, image
