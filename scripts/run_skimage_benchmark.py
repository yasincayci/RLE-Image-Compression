from __future__ import annotations

import csv
import json
from pathlib import Path
import sys

import numpy as np
from PIL import Image
from skimage import data


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from rle_image_compression.pipeline import run_pipeline  # noqa: E402


def _to_uint8(arr: np.ndarray) -> np.ndarray:
    if arr.dtype == np.uint8:
        return arr
    if np.issubdtype(arr.dtype, np.floating):
        arr = np.clip(arr, 0.0, 1.0) * 255.0
    return np.clip(arr, 0, 255).astype(np.uint8)


def _save_skimage_input(name: str, arr: np.ndarray, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    arr = _to_uint8(arr)

    if arr.ndim == 2:
        image = Image.fromarray(arr, mode="L")
    elif arr.ndim == 3 and arr.shape[2] == 3:
        image = Image.fromarray(arr, mode="RGB")
    elif arr.ndim == 3 and arr.shape[2] == 4:
        image = Image.fromarray(arr, mode="RGBA")
    else:
        raise ValueError(f"Unsupported skimage sample shape for {name}: {arr.shape}")

    out_path = out_dir / f"{name}.png"
    image.save(out_path)
    return out_path


if __name__ == "__main__":
    sample_builders = {
        "astronaut": data.astronaut,
        "coffee": data.coffee,
        "chelsea": data.chelsea,
        "rocket": data.rocket,
        "camera": data.camera,
    }

    input_dir = PROJECT_ROOT / "images" / "skimage_inputs"
    all_rows = []

    for sample_name, builder in sample_builders.items():
        input_path = _save_skimage_input(sample_name, builder(), input_dir)
        rows = run_pipeline(PROJECT_ROOT, input_image_path=input_path)
        for r in rows:
            all_rows.append(
                {
                    "sample": sample_name,
                    "scene": r.scene,
                    "bmp_type": r.bmp_type,
                    "scan_mode": r.scan_mode,
                    "original_size_bytes": r.original_size_bytes,
                    "compressed_size_bytes": r.compressed_size_bytes,
                    "compression_rate_percent": r.compression_rate_percent,
                    "compression_performance_percent": r.compression_performance_percent,
                    "lossless": r.lossless,
                }
            )

    results_dir = PROJECT_ROOT / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    csv_path = results_dir / "skimage_benchmark_summary.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(all_rows[0].keys()))
        writer.writeheader()
        for row in all_rows:
            writer.writerow(row)

    json_path = results_dir / "skimage_benchmark_summary.json"
    json_path.write_text(json.dumps(all_rows, indent=2), encoding="utf-8")

    all_lossless = all(row["lossless"] for row in all_rows)
    print(f"Samples: {len(sample_builders)} | rows: {len(all_rows)} | lossless: {all_lossless}")
    print(f"Summary files: {csv_path.name}, {json_path.name}")