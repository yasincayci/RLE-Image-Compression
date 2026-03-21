from __future__ import annotations

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from rle_image_compression.image_generator import generate_dataset_sources  # noqa: E402


if __name__ == "__main__":
    sources = generate_dataset_sources(PROJECT_ROOT, size=512)
    print(f"Generated {len(sources)} source images at images/generated_sources")
