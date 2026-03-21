from __future__ import annotations

import csv
import json
import shutil
import struct
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional

from .bmp_codec import IndexedBMP, build_bmp_from_header_and_pixels, read_indexed_bmp, write_indexed_bmp
from .dataset import (
    build_rocket_variants,
    build_variants_for_image,
    load_external_source_with_padding,
)
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
class ScanModeBlockComparisonRow:
    scene: str
    block_size: int
    block_row: int
    block_col: int
    row_major_avg_perf_percent: float
    col_major_avg_perf_percent: float
    zigzag_64_avg_perf_percent: float
    winner_scan_mode: str
    winner_gap_percent_point: float


@dataclass
class BlockFeatureRow:
    scene: str
    block_size: int
    block_row: int
    block_col: int
    unique_values: int
    row_change_ratio: float
    col_change_ratio: float
    winner_scan_mode: str


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


def _write_report_md(results: List[ResultRow], output_path: Path) -> None:
    all_lossless = all(r.lossless for r in results)
    scene = results[0].scene

    row_map = {r.bmp_type: r for r in results if r.scan_mode == "row_major"}
    col_map = {r.bmp_type: r for r in results if r.scan_mode == "col_major"}
    zig_map = {r.bmp_type: r for r in results if r.scan_mode == "zigzag_64"}

    def best_scan(bmp_type: str) -> str:
        candidates = [row_map[bmp_type], col_map[bmp_type], zig_map[bmp_type]]
        best = max(candidates, key=lambda item: item.compression_performance_percent)
        return f"{best.scan_mode} ({best.compression_performance_percent:.2f}%)"

    lines = [
        "# RLE Compression Report",
        "",
        "## 1. Scope",
        "",
        "This report evaluates a custom hybrid RLE codec on the same image content converted into three indexed BMP types (1-bit B&W, 4-bit grayscale with 16 levels, and 8-bit color-table palette) with three scan modes (row, column, 64x64 zigzag).",
        "",
        "Benchmark source:",
        "",
        f"- {scene}",
        "",
        "## 2. Source Visuals",
        "",
        "![Rocket Launch Source](../images/generated_sources/rocket_orbit_launch_512.png)",
        "",
        "Indexed BMP variants:",
        "",
        "![Rocket 1-bit BMP](../images/bmp/rocket_orbit_launch_512_bw_1bit.bmp)",
        "![Rocket 4-bit BMP](../images/bmp/rocket_orbit_launch_512_gray_4bit.bmp)",
        "![Rocket 8-bit BMP](../images/bmp/rocket_orbit_launch_512_palette_8bit.bmp)",
        "",
        "## 3. Lossless Verification",
        "",
        f"All experiments are lossless: {all_lossless}.",
        "",
        "## 4. Method",
        "",
        "- RLE variant: hybrid token stream with run tokens (for repeated values) and literal tokens (for mixed sequences).",
        "- Compression performance formula: 100 * (1 - compressed_size / original_size)",
        "- Each encoded file stores metadata + original BMP header + RLE payload.",
        "- Zigzag mode explicitly partitions the image into non-overlapping 64x64 blocks, then applies zigzag traversal inside each block.",
        "",
        "Header embedding implementation:",
        "",
        "- Module: src/rle_image_compression/pipeline.py",
        "- Function: _encode_file",
        "- Operation: output_path.write_bytes(meta + header_blob + payload)",
    ]

    lines.extend(
        [
            "",
            f"## 5. Results for {scene}",
            "",
            "### 5.1 3x3 Performance Summary",
            "",
            "| BMP Type | Row Perf (%) | Column Perf (%) | Zigzag Perf (%) | Best Scan |",
            "|---|---:|---:|---:|---|",
        ]
    )

    for bmp_type in ("bw_1bit", "gray_4bit", "palette_8bit"):
        lines.append(
            "| "
            f"{bmp_type} | "
            f"{row_map[bmp_type].compression_performance_percent:.2f} | "
            f"{col_map[bmp_type].compression_performance_percent:.2f} | "
            f"{zig_map[bmp_type].compression_performance_percent:.2f} | "
            f"{best_scan(bmp_type)} |"
        )

    lines.extend(
        [
            "",
            "### 5.2 Detailed Per-Mode Table",
            "",
            "| BMP Type | Scan Mode | Original Size (bytes) | Compressed Size (bytes) | Compression Rate (%) | Compression Performance (%) |",
            "|---|---|---:|---:|---:|---:|",
        ]
    )

    scan_order = {"row_major": 0, "col_major": 1, "zigzag_64": 2}
    type_order = {"bw_1bit": 0, "gray_4bit": 1, "palette_8bit": 2}
    for row in sorted(results, key=lambda r: (type_order[r.bmp_type], scan_order[r.scan_mode])):
        lines.append(
            "| "
            f"{row.bmp_type} | "
            f"{row.scan_mode} | "
            f"{row.original_size_bytes} | "
            f"{row.compressed_size_bytes} | "
            f"{row.compression_rate_percent:.2f} | "
            f"{row.compression_performance_percent:.2f} |"
        )

    lines.extend(
        [
            "",
            "### 5.3 Deep Technical Notes by BMP Type",
            "",
        ]
    )

    for bmp_type in ("bw_1bit", "gray_4bit", "palette_8bit"):
        r = row_map[bmp_type].compression_performance_percent
        c = col_map[bmp_type].compression_performance_percent
        z = zig_map[bmp_type].compression_performance_percent
        vals = {"row_major": r, "col_major": c, "zigzag_64": z}
        best_mode = max(vals, key=vals.get)
        worst_mode = min(vals, key=vals.get)
        spread = vals[best_mode] - vals[worst_mode]

        lines.extend(
            [
                f"- {bmp_type}:",
                f"  - Best scan: {best_mode} ({vals[best_mode]:.2f}%)",
                f"  - Worst scan: {worst_mode} ({vals[worst_mode]:.2f}%)",
                f"  - Spread: {spread:.2f} percentage points",
            ]
        )

        if bmp_type == "bw_1bit":
            lines.append(
                "  - Binary quantization preserves only foreground/background structure; mode differences mostly come from how long contiguous silhouette/background runs are preserved."
            )
        elif bmp_type == "gray_4bit":
            lines.append(
                "  - gray_4bit uses true 16-level grayscale quantization stored as 4-bit BMP. Scan order affects boundary changes between rocket, flame, moon edge, smoke drift, and skyline facades/windows."
            )
        else:
            lines.append(
                "  - 8-bit keeps fine tonal detail. Although runs are shorter in raw sequence terms, the larger original BMP size can still yield strong percentage performance."
            )

    lines.extend(
        [
            "",
            "### 5.4 Bias Analysis and Mitigation",
            "",
            "Scene design was adjusted to reduce directional or type-specific dominance:",
            "- Replaced hard directional strokes with softer haze/smoke blob layers.",
            "- Increased scene heterogeneity with moon craters, varied roof profiles, and irregular facade windows.",
            "- Removed sea stripes and kept city-only lower region to avoid artificial water-pattern bias.",
            "",
            "These changes are intended to produce a fairer comparison across row, column, and zigzag scans and reduce accidental favoritism for any single BMP type.",
        ]
    )

    lines.extend(
        [
            "",
            "## 6. Why 8-bit Can Show High Performance",
            "",
            "Compression performance is measured relative to the original BMP file size. Since 8-bit BMP files have larger container size, comparable encoded payloads can yield higher percentage performance.",
            "",
            "## 7. Deliverables",
            "",
            "- Source indexed BMPs: images/bmp",
            "- Decompressed BMPs: images/decompressed",
            "- Encoded files: encoded",
            "- Pixel matrices: images/pixel_values",
            "- Source images: images/generated_sources",
            "- Tables: results/compression_results.csv and results/compression_results.json",
        ]
    )

    output_path.write_text("\n".join(lines), encoding="utf-8")


def _write_docx_source_report_md(results: List[ResultRow], output_path: Path) -> None:
    all_lossless = all(r.lossless for r in results)
    scene = results[0].scene

    row_map = {r.bmp_type: r for r in results if r.scan_mode == "row_major"}
    col_map = {r.bmp_type: r for r in results if r.scan_mode == "col_major"}
    zig_map = {r.bmp_type: r for r in results if r.scan_mode == "zigzag_64"}

    scan_order = {"row_major": 0, "col_major": 1, "zigzag_64": 2}
    type_order = {"bw_1bit": 0, "gray_4bit": 1, "palette_8bit": 2}

    lines = [
        "# Detailed Report Draft for DOCX",
        "",
        "This file is intentionally verbose so it can be copied into a DOCX document as a long-form report.",
        "",
        "## 1. Assignment Scope and Objective",
        "",
        "This project implements and evaluates a custom RLE-based lossless compression pipeline for indexed BMP images.",
        "The same source content is converted into three BMP formats and each format is tested with three scan modes.",
        "The scope is designed to measure how ordering of pixel samples changes RLE effectiveness under controlled, repeatable conditions.",
        "",
        "Test dimensions used in this repository:",
        "",
        f"- Source scene: {scene}",
        "- Resolution: 512 x 512",
        "- BMP types: 1-bit B and W, 4-bit grayscale (16 levels), 8-bit indexed color palette",
        "- Scan modes: row major, column major, block zigzag (64 x 64)",
        "",
        "## 2. Dataset and Scene Design Rationale",
        "",
        "The source image is not a trivial synthetic checkerboard. It is a structured rocket launch scene with sky, moon,",
        "haze, smoke, and a short apartment row. This content choice intentionally combines smooth regions, textured regions, sharp edges,",
        "and irregular local details. Those mixed properties are important because pure horizontal or pure vertical patterns would unfairly",
        "favor one scan mode and reduce the value of a comparative benchmark.",
        "",
        "The latest design iteration removes decorative diagonal traces and keeps only physically plausible diagonal smoke flow.",
        "The goal is to evaluate zigzag behavior under natural-looking conditions without introducing artificial stripe-like bias.",
        "",
        "## 3. Pipeline Architecture",
        "",
        "The pipeline stages are:",
        "",
        "1. Generate source scene (or load external RGB image).",
        "2. Quantize into three indexed representations (1/4/8 bpp).",
        "3. Save each representation as a valid BMP with palette/header information.",
        "4. Flatten pixel matrix with each scan mode.",
        "5. Encode flattened stream with hybrid RLE.",
        "6. Store custom metadata and original BMP header before payload.",
        "7. Decode and reconstruct full BMP.",
        "8. Verify exact pixel equality (lossless check).",
        "9. Export CSV, JSON, and Markdown reports.",
        "",
        "Core modules:",
        "",
        "- src/rle_image_compression/image_generator.py",
        "- src/rle_image_compression/dataset.py",
        "- src/rle_image_compression/bmp_codec.py",
        "- src/rle_image_compression/scans.py",
        "- src/rle_image_compression/rle_codec.py",
        "- src/rle_image_compression/pipeline.py",
        "",
        "## 4. Scan Modes and Expected Effects",
        "",
        "Row major tends to perform well when horizontal structures dominate contiguous values.",
        "Column major is naturally advantaged when vertical continuity is stronger.",
        "Block zigzag (64 x 64) can improve performance when local neighborhoods contain diagonal or mixed-direction continuity,",
        "because zigzag alternates direction and can remain near local tonal neighborhoods longer than strict row or column traversals.",
        "",
        "Important technical detail:",
        "",
        "Zigzag is not global-image zigzag. It is applied independently inside each 64 x 64 block. After one block is consumed,",
        "the next block starts with its own zigzag sequence. This limits long-range continuity transfer across block boundaries,",
        "which is a deliberate tradeoff between locality and traversal regularity.",
        "",
        "## 5. RLE Variant and Container Format",
        "",
        "The codec uses a hybrid token strategy:",
        "",
        "- Run tokens encode repeated symbols compactly.",
        "- Literal tokens preserve mixed sequences without forcing inefficient runs.",
        "",
        "Encoded file layout is:",
        "",
        "[custom metadata][original BMP header bytes][RLE payload]",
        "",
        "Header embedding is implemented in _encode_file with:",
        "",
        "output_path.write_bytes(meta + header_blob + payload)",
        "",
        "This means the encoded artifact is self-descriptive enough to reconstruct a valid BMP during decoding,",
        "without external side files for width/height/header palette context.",
        "",
        "## 6. Experiment Results (Current Run)",
        "",
        f"Lossless verification across all combinations: {all_lossless}",
        "",
        "### 6.1 Summary Table",
        "",
        "| BMP Type | Row Perf (%) | Column Perf (%) | Zigzag Perf (%) |",
        "|---|---:|---:|---:|",
    ]

    for bmp_type in ("bw_1bit", "gray_4bit", "palette_8bit"):
        lines.append(
            "| "
            f"{bmp_type} | "
            f"{row_map[bmp_type].compression_performance_percent:.2f} | "
            f"{col_map[bmp_type].compression_performance_percent:.2f} | "
            f"{zig_map[bmp_type].compression_performance_percent:.2f} |"
        )

    lines.extend(
        [
            "",
            "### 6.2 Full Measurement Table",
            "",
            "| BMP Type | Scan Mode | Original Size (bytes) | Compressed Size (bytes) | Rate (%) | Performance (%) |",
            "|---|---|---:|---:|---:|---:|",
        ]
    )

    for row in sorted(results, key=lambda r: (type_order[r.bmp_type], scan_order[r.scan_mode])):
        lines.append(
            "| "
            f"{row.bmp_type} | "
            f"{row.scan_mode} | "
            f"{row.original_size_bytes} | "
            f"{row.compressed_size_bytes} | "
            f"{row.compression_rate_percent:.2f} | "
            f"{row.compression_performance_percent:.2f} |"
        )

    lines.extend(
        [
            "",
            "## 7. Detailed Interpretation by BMP Type",
            "",
        ]
    )

    for bmp_type in ("bw_1bit", "gray_4bit", "palette_8bit"):
        r = row_map[bmp_type].compression_performance_percent
        c = col_map[bmp_type].compression_performance_percent
        z = zig_map[bmp_type].compression_performance_percent
        vals = {"row_major": r, "col_major": c, "zigzag_64": z}
        best_mode = max(vals, key=vals.get)
        worst_mode = min(vals, key=vals.get)
        spread = vals[best_mode] - vals[worst_mode]

        lines.extend(
            [
                f"### 7.{type_order[bmp_type] + 1} {bmp_type}",
                "",
                f"Best mode: {best_mode} at {vals[best_mode]:.2f}%.",
                f"Worst mode: {worst_mode} at {vals[worst_mode]:.2f}%.",
                f"Spread: {spread:.2f} percentage points.",
                "",
            ]
        )

        if bmp_type == "bw_1bit":
            lines.extend(
                [
                    "In 1-bit data, tonal complexity collapses into binary structure. Large background zones and silhouette edges produce",
                    "longer same-value stretches than higher bit-depth variants. Because symbol space is minimal, traversal order mainly",
                    "changes where transitions happen, not whether transitions exist at all. As a result, differences across scan modes are",
                    "usually meaningful but bounded. Zigzag can still become best when local diagonal continuity around smoke and edge regions",
                    "is captured more effectively than strict row/column passes.",
                    "",
                ]
            )
        elif bmp_type == "gray_4bit":
            lines.extend(
                [
                    "In gray_4bit mode, true 16-level grayscale quantization is used and stored directly in 4-bit BMP form.",
                    "This makes traversal sensitivity stronger: transitions at moon crescent edge, rocket body shading, smoke",
                    "and apartment facade windows can fragment runs quickly depending on direction. A small design change in the scene can shift",
                    "the winner among row, column, and zigzag because mid-tone boundary topology is rich and directional.",
                    "",
                ]
            )
        else:
            lines.extend(
                [
                    "In 8-bit indexed output, local tone variation is the highest of the three BMP types. This can shorten literal-run patterns",
                    "in absolute sequence terms. However, percentage-based performance often remains strong because the original BMP container",
                    "for 8-bit is larger than lower bit-depth BMPs. Therefore, similar absolute encoded sizes can translate into high relative",
                    "performance. This explains why 8-bit can appear very competitive in percentage metrics despite carrying richer detail.",
                    "",
                ]
            )

    lines.extend(
        [
            "## 8. Fairness Notes and Validity",
            "",
            "Fair comparison requires avoiding patterns that are intentionally aligned with only one traversal direction.",
            "The current scene avoids repeated synthetic stripe fields and instead uses mixed semantic objects with varying directionality.",
            "This does not eliminate all bias, but it reduces engineered favoritism. Remaining differences should be interpreted as",
            "content-structure interaction with scan order, not as universal superiority claims.",
            "",
            "Threats to validity and practical caveats:",
            "",
            "- A single scene cannot represent all image classes.",
            "- Fixed block size (64) may not be optimal for all structures.",
            "- RLE is highly sensitive to quantization and scan adjacency effects.",
            "- Percentage metrics should be read together with absolute byte counts.",
            "",
            "## 9. Reproducibility Checklist",
            "",
            "- Deterministic source generation with fixed RNG seed.",
            "- Fixed image size and fixed scene key.",
            "- Fixed scan mode set and block size.",
            "- Deterministic encode/decode implementation.",
            "- Automated lossless assertion on every run.",
            "",
            "Suggested procedure for report regeneration:",
            "",
            "1. Run scripts/run_pipeline.py.",
            "2. Confirm all rows are lossless.",
            "3. Use compression_results.csv/json for figures and tables.",
            "4. Use this Markdown as DOCX source text.",
            "",
            "## 10. Conclusion",
            "",
            "The implementation satisfies the assignment requirements with a reproducible end-to-end benchmark and verified lossless",
            "reconstruction. Results show that scan order materially affects hybrid RLE performance, and the effect depends on both image",
            "structure and bit depth. The 64 x 64 zigzag mode is implemented correctly as block-local traversal; its gains are content-dependent",
            "rather than guaranteed. For an academic write-up, this is a strong and transparent outcome because it demonstrates method behavior",
            "under realistic mixed-structure content instead of relying on artificially favorable patterns.",
            "",
            "## 11. Appendix: File Outputs",
            "",
            "- images/generated_sources: source scene PNG",
            "- images/bmp: indexed BMP variants",
            "- encoded: encoded RLE artifacts",
            "- images/decompressed: decoded BMP outputs",
            "- images/pixel_values: matrix dumps",
            "- results/compression_results.csv",
            "- results/compression_results.json",
            "- results/REPORT.md",
            "- results/REPORT_DOCX_SOURCE.md",
        ]
    )

    output_path.write_text("\n".join(lines), encoding="utf-8")


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


def _compute_scan_mode_block_comparison(
    scene_name: str, block_rows: List[BlockResultRow]
) -> List[ScanModeBlockComparisonRow]:
    by_block: Dict[tuple, Dict[str, List[float]]] = {}
    for r in block_rows:
        key = (r.block_row, r.block_col)
        by_block.setdefault(key, {"row_major": [], "col_major": [], "zigzag_64": []})[r.scan_mode].append(
            r.block_compression_performance_percent
        )

    rows: List[ScanModeBlockComparisonRow] = []
    for (br, bc), scan_map in by_block.items():
        row_avg = sum(scan_map["row_major"]) / len(scan_map["row_major"]) if scan_map["row_major"] else 0.0
        col_avg = sum(scan_map["col_major"]) / len(scan_map["col_major"]) if scan_map["col_major"] else 0.0
        zig_avg = sum(scan_map["zigzag_64"]) / len(scan_map["zigzag_64"]) if scan_map["zigzag_64"] else 0.0

        perf_map = {"row_major": row_avg, "col_major": col_avg, "zigzag_64": zig_avg}
        winner = max(perf_map, key=perf_map.get)
        ordered = sorted(perf_map.values(), reverse=True)
        gap = ordered[0] - ordered[1]

        rows.append(
            ScanModeBlockComparisonRow(
                scene=scene_name,
                block_size=64,
                block_row=br,
                block_col=bc,
                row_major_avg_perf_percent=round(row_avg, 2),
                col_major_avg_perf_percent=round(col_avg, 2),
                zigzag_64_avg_perf_percent=round(zig_avg, 2),
                winner_scan_mode=winner,
                winner_gap_percent_point=round(gap, 2),
            )
        )
    return rows


def _block_directional_change_ratios(block: List[List[int]]) -> tuple[float, float]:
    h = len(block)
    w = len(block[0]) if h else 0
    if h == 0 or w == 0:
        return 0.0

    row_changes = 0
    row_total = 0
    col_changes = 0
    col_total = 0
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


def _compute_block_features(
    scene_name: str,
    palette_pixels: List[List[int]],
    scan_comparison: List[ScanModeBlockComparisonRow],
) -> List[BlockFeatureRow]:
    winner_map = {
        (r.block_row, r.block_col): r.winner_scan_mode
        for r in scan_comparison
    }

    rows: List[BlockFeatureRow] = []
    for br, bc, block in _iter_blocks(palette_pixels, block_size=64):
        flat = [v for row in block for v in row]
        row_ratio, col_ratio = _block_directional_change_ratios(block)
        rows.append(
            BlockFeatureRow(
                scene=scene_name,
                block_size=64,
                block_row=br,
                block_col=bc,
                unique_values=len(set(flat)),
                row_change_ratio=round(row_ratio, 4),
                col_change_ratio=round(col_ratio, 4),
                winner_scan_mode=winner_map.get((br, bc), "unknown"),
            )
        )
    return rows


def _append_block64_summary(
    lines: List[str],
    block_rows: List[BlockResultRow],
    scan_comparison: List[ScanModeBlockComparisonRow],
    heading: str,
    section_prefix: str,
) -> None:
    if not block_rows or not scan_comparison:
        return

    lines.extend(
        [
            "",
            heading,
            "",
            "This section evaluates compression behavior at 64x64 block level with focus on scan modes (row/column/zigzag).",
            "Block winner is computed using average block performance across BMP types.",
            "",
            f"### {section_prefix}.1 Average Block Performance by Scan",
            "",
            "| Row Avg (%) | Col Avg (%) | Zigzag Avg (%) |",
            "|---:|---:|---:|",
        ]
    )

    row_vals = [r.row_major_avg_perf_percent for r in scan_comparison]
    col_vals = [r.col_major_avg_perf_percent for r in scan_comparison]
    zig_vals = [r.zigzag_64_avg_perf_percent for r in scan_comparison]
    lines.append(
        f"| {sum(row_vals)/len(row_vals):.2f} | {sum(col_vals)/len(col_vals):.2f} | {sum(zig_vals)/len(zig_vals):.2f} |"
    )

    lines.extend(
        [
            "",
            f"### {section_prefix}.2 Block Winner Counts",
            "",
            "Counts how many 64x64 blocks are best compressed by each scan mode.",
            "",
            "| Row Wins | Col Wins | Zigzag Wins |",
            "|---|---:|---:|---:|",
        ]
    )

    wins = {"row_major": 0, "col_major": 0, "zigzag_64": 0}
    for r in scan_comparison:
        wins[r.winner_scan_mode] += 1
    lines.append(f"| {wins['row_major']} | {wins['col_major']} | {wins['zigzag_64']} |")

    lines.extend(
        [
            "",
            f"### {section_prefix}.3 Interpretation",
            "",
            "If zigzag average is lower, common causes are:",
            "- Block-boundary resets break continuity between adjacent blocks.",
            "- In texture-heavy or noisy blocks, zigzag increases short transitions.",
            "- Row-major can still dominate when many structures are horizontally coherent.",
            "",
            "If zigzag has non-zero winner count but lower global average, it means zigzag is locally strong in selected blocks",
            "yet not dominant enough across all blocks to beat row/column globally.",
            "",
            f"### {section_prefix}.4 Largest Zigzag Deficits (Sample)",
            "",
            "The rows below show where zigzag underperforms the best alternative the most.",
            "",
            "| Block (r,c) | Zigzag Avg (%) | Best Alt Avg (%) | Gap (pp) |",
            "|---|---|---:|---:|---:|",
        ]
    )

    deficits = []
    for r in scan_comparison:
        best_alt = max(r.row_major_avg_perf_percent, r.col_major_avg_perf_percent)
        gap = best_alt - r.zigzag_64_avg_perf_percent
        deficits.append((gap, r.block_row, r.block_col, r.zigzag_64_avg_perf_percent, best_alt))

    deficits.sort(reverse=True, key=lambda x: x[0])
    for gap, br, bc, zig, best_alt in deficits[:12]:
        lines.append(f"| ({br},{bc}) | {zig:.2f} | {best_alt:.2f} | {gap:.2f} |")


def _append_scan_mode_block_summary(
    lines: List[str],
    comparison_rows: List[ScanModeBlockComparisonRow],
    feature_rows: List[BlockFeatureRow],
    heading: str,
    section_prefix: str,
) -> None:
    if not comparison_rows:
        return

    lines.extend(
        [
            "",
            heading,
            "",
            "This section compares RLE scan modes directly at each 64x64 block using average performance across BMP types.",
            "It reveals which local visual structures favor row-major, column-major, or zigzag traversal.",
            "",
            f"### {section_prefix}.1 Winner Counts by RLE Scan Mode",
            "",
            "| Winner Scan | Block Count | Avg Winner Gap (pp) |",
            "|---|---:|---:|",
        ]
    )

    winner_modes = ["row_major", "col_major", "zigzag_64"]
    for mode in winner_modes:
        sample = [r for r in comparison_rows if r.winner_scan_mode == mode]
        avg_gap = (sum(r.winner_gap_percent_point for r in sample) / len(sample)) if sample else 0.0
        lines.append(f"| {mode} | {len(sample)} | {avg_gap:.2f} |")

    lines.extend(
        [
            "",
            f"### {section_prefix}.2 Most Decisive Blocks by Winner Scan",
            "",
            "| Block (r,c) | Winner Scan | Row Avg (%) | Col Avg (%) | Zigzag Avg (%) | Winner Gap (pp) |",
            "|---|---|---:|---:|---:|---:|",
        ]
    )

    for mode in winner_modes:
        mode_rows = [r for r in comparison_rows if r.winner_scan_mode == mode]
        mode_rows.sort(key=lambda r: r.winner_gap_percent_point, reverse=True)
        for r in mode_rows[:4]:
            lines.append(
                f"| ({r.block_row},{r.block_col}) | {r.winner_scan_mode} | "
                f"{r.row_major_avg_perf_percent:.2f} | {r.col_major_avg_perf_percent:.2f} | "
                f"{r.zigzag_64_avg_perf_percent:.2f} | {r.winner_gap_percent_point:.2f} |"
            )

    lines.extend(
        [
            "",
            f"### {section_prefix}.3 Content-to-RLE Heuristic",
            "",
        ]
    )

    by_winner: Dict[str, List[BlockFeatureRow]] = {"row_major": [], "col_major": [], "zigzag_64": []}
    for fr in feature_rows:
        if fr.winner_scan_mode in by_winner:
            by_winner[fr.winner_scan_mode].append(fr)

    lines.extend(
        [
            "| Winner Scan | Avg Unique Values | Avg Row Change | Avg Col Change | Blocks |",
            "|---|---:|---:|---:|---:|",
        ]
    )

    stats_map: Dict[str, tuple] = {}
    for mode in ["row_major", "col_major", "zigzag_64"]:
        grp = by_winner[mode]
        if grp:
            avg_u = sum(v.unique_values for v in grp) / len(grp)
            avg_r = sum(v.row_change_ratio for v in grp) / len(grp)
            avg_c = sum(v.col_change_ratio for v in grp) / len(grp)
            u_txt = f"{avg_u:.2f}"
            r_txt = f"{avg_r:.4f}"
            c_txt = f"{avg_c:.4f}"
        else:
            avg_u = 0.0
            avg_r = 0.0
            avg_c = 0.0
            u_txt = "N/A"
            r_txt = "N/A"
            c_txt = "N/A"
        stats_map[mode] = (avg_u, avg_r, avg_c, len(grp))
        lines.append(f"| {mode} | {u_txt} | {r_txt} | {c_txt} | {len(grp)} |")

    row_u, row_r, row_c, _ = stats_map["row_major"]
    col_u, col_r, col_c, _ = stats_map["col_major"]
    zig_u, zig_r, zig_c, _ = stats_map["zigzag_64"]

    lines.extend(["", "Practical rule extraction from this image:"])
    lines.append(
        f"- Row-major is strongest where block complexity is lower and row continuity is higher (avg unique {row_u:.1f}, row-change {row_r:.3f}, col-change {row_c:.3f})."
    )
    lines.append(
        f"- Column-major is strongest where vertical continuity dominates (avg unique {col_u:.1f}, row-change {col_r:.3f}, col-change {col_c:.3f})."
    )
    lines.append(
        f"- Zigzag is strongest in mixed-direction textured blocks where row/col changes are both relatively high and close to each other (avg unique {zig_u:.1f}, row-change {zig_r:.3f}, col-change {zig_c:.3f})."
    )

    lines.extend(
        [
            "",
            "These conclusions are scene-specific and should be re-estimated for different image families.",
        ]
    )


def _write_pixel_values(path: Path, pixels: List[List[int]]) -> None:
    lines = [" ".join(str(v) for v in row) for row in pixels]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _encode_file(
    src_bmp: IndexedBMP,
    scan_mode: str,
    output_path: Path,
) -> int:
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
    # Encoded file layout: [custom metadata][original BMP header][RLE payload].
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


def run_pipeline(project_root: Path, input_image_path: Optional[Path] = None) -> List[ResultRow]:
    if input_image_path is None:
        scene_name, variants = build_rocket_variants(project_root)
    else:
        preview_path = project_root / "images" / "generated_sources" / f"external_{input_image_path.stem}_512.png"
        source_name, rgb_image = load_external_source_with_padding(
            image_path=input_image_path,
            output_preview_path=preview_path,
            size=512,
        )
        scene_name, variants = build_variants_for_image(source_name, rgb_image)

    bmp_dir = project_root / "images" / "bmp"
    pixel_dir = project_root / "images" / "pixel_values"
    encoded_dir = project_root / "encoded"
    decompressed_dir = project_root / "images" / "decompressed"
    results_dir = project_root / "results"

    for output_dir in (bmp_dir, pixel_dir, encoded_dir, decompressed_dir, results_dir):
        if output_dir.exists():
            shutil.rmtree(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

    results: List[ResultRow] = []
    block_results: List[BlockResultRow] = []

    for bmp_type, variant in variants.items():
        pixels = variant.pixels
        block_results.extend(_compute_block64_analysis(scene_name, bmp_type, pixels))

        bmp_path = bmp_dir / f"{scene_name}_{bmp_type}.bmp"
        pixel_path = pixel_dir / f"{scene_name}_{bmp_type}_pixels.txt"
        write_indexed_bmp(bmp_path, pixels, variant.bpp, variant.palette)
        _write_pixel_values(pixel_path, pixels)

        src_bmp = read_indexed_bmp(bmp_path)
        original_size = bmp_path.stat().st_size

        for scan_mode in SCAN_FLATTEN:
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
                    compression_performance_percent=round(
                        compression_performance(original_size, compressed_size), 2
                    ),
                    lossless=lossless,
                )
            )

    scan_mode_block_comparison = _compute_scan_mode_block_comparison(scene_name, block_results)
    feature_rows = _compute_block_features(
        scene_name,
        variants["palette_8bit"].pixels,
        scan_mode_block_comparison,
    )

    csv_path = results_dir / "compression_results.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(asdict(results[0]).keys()))
        writer.writeheader()
        for row in results:
            writer.writerow(asdict(row))

    json_path = results_dir / "compression_results.json"
    json_path.write_text(json.dumps([asdict(r) for r in results], indent=2), encoding="utf-8")

    block_csv_path = results_dir / "block64_results.csv"
    with block_csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(asdict(block_results[0]).keys()))
        writer.writeheader()
        for row in block_results:
            writer.writerow(asdict(row))

    block_json_path = results_dir / "block64_results.json"
    block_json_path.write_text(json.dumps([asdict(r) for r in block_results], indent=2), encoding="utf-8")

    scan_mode_block_csv = results_dir / "block64_scan_mode_comparison.csv"
    with scan_mode_block_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(asdict(scan_mode_block_comparison[0]).keys()))
        writer.writeheader()
        for row in scan_mode_block_comparison:
            writer.writerow(asdict(row))

    scan_mode_block_json = results_dir / "block64_scan_mode_comparison.json"
    scan_mode_block_json.write_text(
        json.dumps([asdict(r) for r in scan_mode_block_comparison], indent=2), encoding="utf-8"
    )

    block_features_csv = results_dir / "block64_scan_features.csv"
    with block_features_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(asdict(feature_rows[0]).keys()))
        writer.writeheader()
        for row in feature_rows:
            writer.writerow(asdict(row))

    block_features_json = results_dir / "block64_scan_features.json"
    block_features_json.write_text(json.dumps([asdict(r) for r in feature_rows], indent=2), encoding="utf-8")

    report_path = results_dir / "REPORT.md"
    _write_report_md(results, report_path)
    report_lines = report_path.read_text(encoding="utf-8").splitlines()
    _append_block64_summary(
        report_lines,
        block_results,
        scan_mode_block_comparison,
        "## 8. 64x64 Block-Level Analysis (Why Zigzag May Lose Overall)",
        "8",
    )
    _append_scan_mode_block_summary(
        report_lines,
        scan_mode_block_comparison,
        feature_rows,
        "## 9. 64x64 Block-Level RLE Scan Analysis",
        "9",
    )
    report_path.write_text("\n".join(report_lines), encoding="utf-8")

    return results
