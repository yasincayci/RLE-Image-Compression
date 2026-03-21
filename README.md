# RLE Image Compression (BMP + Scan Modes)

This project benchmarks lossless hybrid RLE compression on indexed BMP images using three scan modes.

- BMP formats: `bw_1bit`, `gray_4bit`, `palette_8bit`
- Scan modes (RLE traversal): `row_major`, `col_major`, `zigzag_64`
- Source: default `skimage_rocket` (or user image with `--input-image`)
- Preprocess canvas: `256x256` (aspect-ratio preserved + padded, 64x64 zigzag-aligned)
- Validation: decode output is checked pixel-by-pixel (lossless)

## Run

```bash
pip install -r requirements.txt
python run_pipeline.py
```

Optional external input:

```bash
python run_pipeline.py --input-image path/to/image.png
```

## Project Layout

Requested pipe-style structure:

```text
|
|-- run_pipeline.py
|
|-- src
|   |
|   |----- rle_image_compression
|          |--------- dataset.py
|          |--------- bmp_codec.py
|          |--------- scans.py
|          |--------- rle_codec.py
|          |--------- pipeline.py
|
|-- images
|   |
|   |----- generated_sources
|   |----- previews
|   |----- bmp
|   |----- decompressed
|   |----- pixel_values
|
|-- results
|   |
|   |----- compression_results.csv
|   |----- compression_results.json
|   |----- block64_results.csv
|   |----- block64_bmp_scan_comparison.csv
|   |----- bmp_scan_summary.csv
|   |----- results_tables.md
```

## Report Strategy (Not Pushed)

Report generation logic is moved to a local-only area and excluded from git:

- Local report builder code: `local/reporting/report_builder.py`
- Local report output: `local/reports/REPORT.md`
- Git behavior: `local/` is ignored in [\.gitignore](.gitignore)

This keeps report creation available on your machine without pushing report tooling/artifacts.

## Source and BMP Visuals

Default source image:

![source](images/generated_sources/skimage_rocket_256.png)

BMP-type preview images (PNG previews so GitHub renders correctly):

### bw_1bit
![bw_1bit](images/previews/skimage_rocket_bw_1bit.png)

### gray_4bit
![gray_4bit](images/previews/skimage_rocket_gray_4bit.png)

### palette_8bit
![palette_8bit](images/previews/skimage_rocket_palette_8bit.png)

## Main Results (Markdown Tables)

### Global Performance by BMP Type

| BMP Type | Row Major (%) | Col Major (%) | Zigzag 64 (%) | Best Scan |
|---|---:|---:|---:|---|
| bw_1bit | 76.19 | 80.05 | 68.89 | col_major |
| gray_4bit | 37.90 | 39.94 | 26.13 | col_major |
| palette_8bit | 29.26 | 21.11 | 18.62 | row_major |

### Block-Winner Counts by BMP Type (64x64)

| BMP Type | Row Wins | Col Wins | Zigzag Wins |
|---|---:|---:|---:|
| bw_1bit | 11 | 5 | 0 |
| gray_4bit | 7 | 9 | 0 |
| palette_8bit | 13 | 2 | 1 |

### Full 3x3 Matrix

| BMP Type | Scan Mode | Original (bytes) | Compressed (bytes) | Compression Rate (%) | Compression Performance (%) | Lossless |
|---|---|---:|---:|---:|---:|---|
| bw_1bit | row_major | 8254 | 1965 | 23.81 | 76.19 | True |
| bw_1bit | col_major | 8254 | 1647 | 19.95 | 80.05 | True |
| bw_1bit | zigzag_64 | 8254 | 2568 | 31.11 | 68.89 | True |
| gray_4bit | row_major | 32886 | 20423 | 62.10 | 37.90 | True |
| gray_4bit | col_major | 32886 | 19751 | 60.06 | 39.94 | True |
| gray_4bit | zigzag_64 | 32886 | 24293 | 73.87 | 26.13 | True |
| palette_8bit | row_major | 66614 | 47123 | 70.74 | 29.26 | True |
| palette_8bit | col_major | 66614 | 52551 | 78.89 | 21.11 | True |
| palette_8bit | zigzag_64 | 66614 | 54210 | 81.38 | 18.62 | True |

## Interpretation: Which Format + Which RLE Traversal Works Better?

- `bw_1bit`: `col_major` works best globally.
- `gray_4bit`: `col_major` works best globally.
- `palette_8bit`: `row_major` works best globally.

Block-level behavior is format-dependent and does not always match a single universal winner across all BMP types.

## Output Files

- [results/compression_results.csv](results/compression_results.csv)
- [results/compression_results.json](results/compression_results.json)
- [results/block64_results.csv](results/block64_results.csv)
- [results/block64_results.json](results/block64_results.json)
- [results/block64_bmp_scan_comparison.csv](results/block64_bmp_scan_comparison.csv)
- [results/block64_bmp_scan_comparison.json](results/block64_bmp_scan_comparison.json)
- [results/block64_value_features.csv](results/block64_value_features.csv)
- [results/block64_value_features.json](results/block64_value_features.json)
- [results/bmp_scan_summary.csv](results/bmp_scan_summary.csv)
- [results/bmp_scan_summary.json](results/bmp_scan_summary.json)
- [results/results_tables.md](results/results_tables.md)
