from __future__ import annotations

import argparse
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from rle_image_compression.pipeline import run_pipeline  # noqa: E402


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run RLE benchmark pipeline")
    parser.add_argument(
        "--input-image",
        type=str,
        default=None,
        help="Optional external image path. If omitted, skimage rocket is used by default. Input is resized/padded to 512x512.",
    )
    args = parser.parse_args()

    input_image = Path(args.input_image).resolve() if args.input_image else None
    if input_image is not None and not input_image.exists():
        raise FileNotFoundError(f"Input image not found: {input_image}")

    results = run_pipeline(PROJECT_ROOT, input_image_path=input_image)
    all_lossless = all(r.lossless for r in results)
    print(f"Generated {len(results)} experiment rows. Lossless: {all_lossless}")
