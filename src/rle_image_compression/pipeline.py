from __future__ import annotations

import csv
import importlib.util
import json
import shutil
import struct
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PIL import Image

from .bmp_codec import IndexedBMP, build_bmp_from_header_and_pixels, read_indexed_bmp, write_indexed_bmp
from .dataset import build_variants_for_image, load_default_skimage_rocket, load_external_source_with_padding
from .rle_codec import compression_performance, compression_rate, decode_rle, encode_rle
from .scans import (
    flatten_block_zigzag,
    flatten_col_major,
    flatten_row_major,
    unflatten_block_zigzag,
    unflatten_col_major,
    unflatten_row_major,
)

MAGIC = b"RLEI"
VERSION = 1
SCAN_TO_ID = {"row_major": 1, "col_major": 2, "zigzag_64": 3}
ID_TO_SCAN = {v: k for k, v in SCAN_TO_ID.items()}
SCAN_ORDER = ["row_major", "col_major", "zigzag_64"]
BMP_ORDER = ["bw_1bit", "gray_4bit", "palette_8bit"]
CANVAS_SIZE = 384


@dataclass
class ResultRow:
    scene: str
    bmp_type: str
    scan_mode: str
    original_size_bytes: int
    compressed_size_bytes: int
    compression_rate_percent: float
    compression_performance_percent: float
    lossless: bool


@dataclass
class BlockResultRow:
    scene: str
    bmp_type: str
    scan_mode: str
    block_size: int
    block_row: int
    block_col: int
    values_count: int
    payload_size_bytes: int
    block_compression_performance_percent: float


@dataclass
class BmpBlockComparisonRow:
    scene: str
    bmp_type: str
    block_size: int
    block_row: int
    block_col: int
    row_major_perf_percent: float
    col_major_perf_percent: float
    zigzag_64_perf_percent: float
    winner_scan_mode: str
    winner_gap_percent_point: float


@dataclass
class BmpTypeSummaryRow:
    scene: str
    bmp_type: str
    best_scan_by_global_performance: str
    row_major_global_perf_percent: float
    col_major_global_perf_percent: float
    zigzag_64_global_perf_percent: float
    row_major_block_wins: int
    col_major_block_wins: int
    zigzag_64_block_wins: int


@dataclass
class BlockValueFeatureRow:
    scene: str
    bmp_type: str
    block_size: int
    block_row: int
    block_col: int
    unique_values: int
    row_change_ratio: float
    col_change_ratio: float
    dominant_direction: str


SCAN_FLATTEN = {
    "row_major": flatten_row_major,
    "col_major": flatten_col_major,
    "zigzag_64": lambda pixels: flatten_block_zigzag(pixels, block_size=64),
}

SCAN_UNFLATTEN = {
    "row_major": unflatten_row_major,
    "col_major": unflatten_col_major,
    "zigzag_64": lambda values, w, h: unflatten_block_zigzag(values, w, h, block_size=64),
}


def _write_pixel_values(path: Path, pixels: List[List[int]]) -> None:
    lines = [" ".join(str(v) for v in row) for row in pixels]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _encode_file(src_bmp: IndexedBMP, scan_mode: str, output_path: Path) -> int:
    values = SCAN_FLATTEN[scan_mode](src_bmp.pixels)
    payload = encode_rle(values)

    header_blob = src_bmp.header_bytes
    meta = struct.pack(
        "<4sBBBBHHII",
        MAGIC,
        VERSION,
        SCAN_TO_ID[scan_mode],
        src_bmp.bpp,
        0,
        src_bmp.width,
        src_bmp.height,
        len(header_blob),
        len(payload),
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(meta + header_blob + payload)
    return len(meta) + len(header_blob) + len(payload)


def _decode_file(encoded_path: Path, output_bmp_path: Path) -> List[List[int]]:
    data = encoded_path.read_bytes()
    meta_size = struct.calcsize("<4sBBBBHHII")
    magic, version, scan_id, bpp, _reserved, width, height, header_len, payload_len = struct.unpack(
        "<4sBBBBHHII", data[:meta_size]
    )

    if magic != MAGIC or version != VERSION:
        raise ValueError("Invalid encoded RLE file")

    header_blob = data[meta_size : meta_size + header_len]
    payload = data[meta_size + header_len : meta_size + header_len + payload_len]

    values = decode_rle(payload, expected_count=width * height)
    scan_mode = ID_TO_SCAN[scan_id]
    pixels = SCAN_UNFLATTEN[scan_mode](values, width, height)

    bmp_bytes = build_bmp_from_header_and_pixels(header_blob, pixels, bpp)
    output_bmp_path.parent.mkdir(parents=True, exist_ok=True)
    output_bmp_path.write_bytes(bmp_bytes)
    return pixels


def _iter_blocks(pixels: List[List[int]], block_size: int = 64):
    h = len(pixels)
    w = len(pixels[0]) if h else 0
    for by in range(0, h, block_size):
        for bx in range(0, w, block_size):
            block = [row[bx : bx + block_size] for row in pixels[by : by + block_size]]
            yield by // block_size, bx // block_size, block


def _compute_block64_analysis(scene_name: str, bmp_type: str, pixels: List[List[int]]) -> List[BlockResultRow]:
    rows: List[BlockResultRow] = []
    for block_row, block_col, block_pixels in _iter_blocks(pixels, block_size=64):
        for scan_mode, flatten in SCAN_FLATTEN.items():
            values = flatten(block_pixels)
            payload = encode_rle(values)
            perf = compression_performance(len(values), len(payload))
            rows.append(
                BlockResultRow(
                    scene=scene_name,
                    bmp_type=bmp_type,
                    scan_mode=scan_mode,
                    block_size=64,
                    block_row=block_row,
                    block_col=block_col,
                    values_count=len(values),
                    payload_size_bytes=len(payload),
                    block_compression_performance_percent=round(perf, 2),
                )
            )
    return rows


def _compute_bmp_block_comparison(
    scene_name: str,
    bmp_type: str,
    block_rows: List[BlockResultRow],
) -> List[BmpBlockComparisonRow]:
    grouped: Dict[Tuple[int, int], Dict[str, float]] = {}
    for r in block_rows:
        if r.bmp_type != bmp_type:
            continue
        key = (r.block_row, r.block_col)
        grouped.setdefault(key, {})[r.scan_mode] = r.block_compression_performance_percent

    rows: List[BmpBlockComparisonRow] = []
    for (block_row, block_col), scan_map in grouped.items():
        row_perf = scan_map.get("row_major", 0.0)
        col_perf = scan_map.get("col_major", 0.0)
        zig_perf = scan_map.get("zigzag_64", 0.0)

        perf_map = {
            "row_major": row_perf,
            "col_major": col_perf,
            "zigzag_64": zig_perf,
        }
        winner = max(perf_map, key=perf_map.get)
        ordered = sorted(perf_map.values(), reverse=True)
        gap = (ordered[0] - ordered[1]) if len(ordered) > 1 else 0.0

        rows.append(
            BmpBlockComparisonRow(
                scene=scene_name,
                bmp_type=bmp_type,
                block_size=64,
                block_row=block_row,
                block_col=block_col,
                row_major_perf_percent=round(row_perf, 2),
                col_major_perf_percent=round(col_perf, 2),
                zigzag_64_perf_percent=round(zig_perf, 2),
                winner_scan_mode=winner,
                winner_gap_percent_point=round(gap, 2),
            )
        )
    return rows


def _compute_bmp_type_summary(
    scene_name: str,
    results: List[ResultRow],
    bmp_block_cmp: List[BmpBlockComparisonRow],
) -> List[BmpTypeSummaryRow]:
    out: List[BmpTypeSummaryRow] = []

    for bmp_type in BMP_ORDER:
        by_scan = {r.scan_mode: r for r in results if r.bmp_type == bmp_type}
        perf_map = {s: by_scan[s].compression_performance_percent for s in SCAN_ORDER}
        best_global = max(perf_map, key=perf_map.get)

        wins = {"row_major": 0, "col_major": 0, "zigzag_64": 0}
        for row in bmp_block_cmp:
            if row.bmp_type == bmp_type:
                wins[row.winner_scan_mode] += 1

        out.append(
            BmpTypeSummaryRow(
                scene=scene_name,
                bmp_type=bmp_type,
                best_scan_by_global_performance=best_global,
                row_major_global_perf_percent=round(perf_map["row_major"], 2),
                col_major_global_perf_percent=round(perf_map["col_major"], 2),
                zigzag_64_global_perf_percent=round(perf_map["zigzag_64"], 2),
                row_major_block_wins=wins["row_major"],
                col_major_block_wins=wins["col_major"],
                zigzag_64_block_wins=wins["zigzag_64"],
            )
        )

    return out


def _block_change_ratios(block: List[List[int]]) -> Tuple[float, float]:
    h = len(block)
    w = len(block[0]) if h else 0
    if h == 0 or w == 0:
        return 0.0, 0.0

    row_total = 0
    row_changes = 0
    col_total = 0
    col_changes = 0

    for y in range(h):
        for x in range(w - 1):
            row_total += 1
            if block[y][x] != block[y][x + 1]:
                row_changes += 1

    for y in range(h - 1):
        for x in range(w):
            col_total += 1
            if block[y][x] != block[y + 1][x]:
                col_changes += 1

    row_ratio = (row_changes / row_total) if row_total else 0.0
    col_ratio = (col_changes / col_total) if col_total else 0.0
    return row_ratio, col_ratio


def _compute_block_value_features(scene_name: str, bmp_type: str, pixels: List[List[int]]) -> List[BlockValueFeatureRow]:
    rows: List[BlockValueFeatureRow] = []
    for block_row, block_col, block in _iter_blocks(pixels, block_size=64):
        flat = [v for row in block for v in row]
        row_ratio, col_ratio = _block_change_ratios(block)

        if abs(row_ratio - col_ratio) <= 0.005:
            dominant = "balanced"
        elif row_ratio < col_ratio:
            dominant = "horizontal_continuity"
        else:
            dominant = "vertical_continuity"

        rows.append(
            BlockValueFeatureRow(
                scene=scene_name,
                bmp_type=bmp_type,
                block_size=64,
                block_row=block_row,
                block_col=block_col,
                unique_values=len(set(flat)),
                row_change_ratio=round(row_ratio, 4),
                col_change_ratio=round(col_ratio, 4),
                dominant_direction=dominant,
            )
        )
    return rows


def _save_indexed_preview_png(path: Path, pixels: List[List[int]], palette: List[Tuple[int, int, int]]) -> None:
    h = len(pixels)
    w = len(pixels[0]) if h else 0
    image = Image.new("P", (w, h))
    image.putdata([v for row in pixels for v in row])

    flat_palette: List[int] = []
    for r, g, b in palette:
        flat_palette.extend([r, g, b])
    while len(flat_palette) < 256 * 3:
        flat_palette.extend([0, 0, 0])

    image.putpalette(flat_palette[: 256 * 3])
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def _write_rows_csv_json(rows: List[object], csv_path: Path, json_path: Path) -> None:
    if not rows:
        return
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(asdict(rows[0]).keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))
    json_path.write_text(json.dumps([asdict(r) for r in rows], indent=2), encoding="utf-8")


def _write_markdown_tables(
    output_path: Path,
    scene_name: str,
    bmp_summary_rows: List[BmpTypeSummaryRow],
    result_rows: List[ResultRow],
) -> None:
    lines = [
        "# Results Tables",
        "",
        f"Scene: {scene_name}",
        "",
        "## BMP-Type Global Performance (RLE Scan Mode Comparison)",
        "",
        "| BMP Type | Row Major (%) | Col Major (%) | Zigzag 64 (%) | Best Scan |",
        "|---|---:|---:|---:|---|",
    ]

    for row in bmp_summary_rows:
        lines.append(
            f"| {row.bmp_type} | {row.row_major_global_perf_percent:.2f} | "
            f"{row.col_major_global_perf_percent:.2f} | {row.zigzag_64_global_perf_percent:.2f} | "
            f"{row.best_scan_by_global_performance} |"
        )

    lines.extend(
        [
            "",
            "## Block-Winner Counts by BMP Type",
            "",
            "| BMP Type | Row Wins | Col Wins | Zigzag Wins |",
            "|---|---:|---:|---:|",
        ]
    )

    for row in bmp_summary_rows:
        lines.append(
            f"| {row.bmp_type} | {row.row_major_block_wins} | {row.col_major_block_wins} | {row.zigzag_64_block_wins} |"
        )

    lines.extend(
        [
            "",
            "## Full 3x3 Result Matrix",
            "",
            "| BMP Type | Scan Mode | Original (bytes) | Compressed (bytes) | Compression Rate (%) | Compression Performance (%) | Lossless |",
            "|---|---|---:|---:|---:|---:|---|",
        ]
    )

    by_order = sorted(
        result_rows,
        key=lambda r: (BMP_ORDER.index(r.bmp_type), SCAN_ORDER.index(r.scan_mode)),
    )
    for row in by_order:
        lines.append(
            f"| {row.bmp_type} | {row.scan_mode} | {row.original_size_bytes} | {row.compressed_size_bytes} | "
            f"{row.compression_rate_percent:.2f} | {row.compression_performance_percent:.2f} | {row.lossless} |"
        )

    output_path.write_text("\n".join(lines), encoding="utf-8")


def _try_generate_local_report(
    project_root: Path,
    scene_name: str,
    results: List[ResultRow],
    block_rows: List[BlockResultRow],
    bmp_block_rows: List[BmpBlockComparisonRow],
    bmp_summary_rows: List[BmpTypeSummaryRow],
    block_value_features: List[BlockValueFeatureRow],
) -> None:
    local_builder = project_root / "local" / "reporting" / "report_builder.py"
    if not local_builder.exists():
        return

    spec = importlib.util.spec_from_file_location("local_report_builder", local_builder)
    if spec is None or spec.loader is None:
        return

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    build_fn = getattr(module, "generate_report", None)
    if build_fn is None:
        return

    out_path = project_root / "local" / "reports" / "REPORT.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    build_fn(
        output_path=out_path,
        scene_name=scene_name,
        results=[asdict(r) for r in results],
        block_rows=[asdict(r) for r in block_rows],
        bmp_block_rows=[asdict(r) for r in bmp_block_rows],
        bmp_summary=[asdict(r) for r in bmp_summary_rows],
        block_value_features=[asdict(r) for r in block_value_features],
    )


def run_pipeline(project_root: Path, input_image_path: Optional[Path] = None) -> List[ResultRow]:
    if input_image_path is None:
        preview_path = project_root / "images" / "generated_sources" / f"skimage_rocket_{CANVAS_SIZE}.png"
        source_name, rgb_image = load_default_skimage_rocket(output_preview_path=preview_path, size=CANVAS_SIZE)
        scene_name, variants = build_variants_for_image(source_name, rgb_image)
    else:
        preview_path = project_root / "images" / "generated_sources" / f"{input_image_path.stem}_{CANVAS_SIZE}.png"
        source_name, rgb_image = load_external_source_with_padding(
            image_path=input_image_path,
            output_preview_path=preview_path,
            size=CANVAS_SIZE,
        )
        scene_name, variants = build_variants_for_image(source_name, rgb_image)

    bmp_dir = project_root / "images" / "bmp"
    preview_dir = project_root / "images" / "previews"
    pixel_dir = project_root / "images" / "pixel_values"
    encoded_dir = project_root / "encoded"
    decompressed_dir = project_root / "images" / "decompressed"
    results_dir = project_root / "results"

    for output_dir in (bmp_dir, preview_dir, pixel_dir, encoded_dir, decompressed_dir, results_dir):
        if output_dir.exists():
            shutil.rmtree(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

    results: List[ResultRow] = []
    block_rows: List[BlockResultRow] = []
    block_value_features: List[BlockValueFeatureRow] = []

    for bmp_type in BMP_ORDER:
        variant = variants[bmp_type]
        pixels = variant.pixels

        bmp_path = bmp_dir / f"{scene_name}_{bmp_type}.bmp"
        png_preview_path = preview_dir / f"{scene_name}_{bmp_type}.png"
        pixel_path = pixel_dir / f"{scene_name}_{bmp_type}_pixels.txt"

        write_indexed_bmp(bmp_path, pixels, variant.bpp, variant.palette)
        _save_indexed_preview_png(png_preview_path, pixels, variant.palette)
        _write_pixel_values(pixel_path, pixels)

        block_rows.extend(_compute_block64_analysis(scene_name, bmp_type, pixels))
        block_value_features.extend(_compute_block_value_features(scene_name, bmp_type, pixels))

        src_bmp = read_indexed_bmp(bmp_path)
        original_size = bmp_path.stat().st_size

        for scan_mode in SCAN_ORDER:
            encoded_path = encoded_dir / scene_name / bmp_type / f"{scan_mode}.rle"
            compressed_size = _encode_file(src_bmp, scan_mode, encoded_path)

            restored_path = decompressed_dir / scene_name / bmp_type / f"{scan_mode}.bmp"
            restored_pixels = _decode_file(encoded_path, restored_path)
            lossless = restored_pixels == src_bmp.pixels

            results.append(
                ResultRow(
                    scene=scene_name,
                    bmp_type=bmp_type,
                    scan_mode=scan_mode,
                    original_size_bytes=original_size,
                    compressed_size_bytes=compressed_size,
                    compression_rate_percent=round(compression_rate(original_size, compressed_size), 2),
                    compression_performance_percent=round(compression_performance(original_size, compressed_size), 2),
                    lossless=lossless,
                )
            )

    bmp_block_rows: List[BmpBlockComparisonRow] = []
    for bmp_type in BMP_ORDER:
        bmp_block_rows.extend(_compute_bmp_block_comparison(scene_name, bmp_type, block_rows))

    bmp_summary = _compute_bmp_type_summary(scene_name, results, bmp_block_rows)

    _write_rows_csv_json(
        results,
        results_dir / "compression_results.csv",
        results_dir / "compression_results.json",
    )
    _write_rows_csv_json(
        block_rows,
        results_dir / "block64_results.csv",
        results_dir / "block64_results.json",
    )
    _write_rows_csv_json(
        bmp_block_rows,
        results_dir / "block64_bmp_scan_comparison.csv",
        results_dir / "block64_bmp_scan_comparison.json",
    )
    _write_rows_csv_json(
        bmp_summary,
        results_dir / "bmp_scan_summary.csv",
        results_dir / "bmp_scan_summary.json",
    )
    _write_rows_csv_json(
        block_value_features,
        results_dir / "block64_value_features.csv",
        results_dir / "block64_value_features.json",
    )

    _write_markdown_tables(
        output_path=results_dir / "results_tables.md",
        scene_name=scene_name,
        bmp_summary_rows=bmp_summary,
        result_rows=results,
    )

    _try_generate_local_report(
        project_root=project_root,
        scene_name=scene_name,
        results=results,
        block_rows=block_rows,
        bmp_block_rows=bmp_block_rows,
        bmp_summary_rows=bmp_summary,
        block_value_features=block_value_features,
    )

    return results
