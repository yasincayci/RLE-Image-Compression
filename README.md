# BMP RLE Scan Benchmark

This repository benchmarks lossless RLE compression for indexed BMP images with three scan modes:

- row_major
- col_major
- zigzag_64 (applied per 64x64 block)

The pipeline generates one source scene and evaluates three BMP types:

- bw_1bit
- gray_4bit
- palette_8bit

BMP variant definitions used in code:

- bw_1bit: binary thresholded black/white image (BMP 1-bit). During RLE stream processing, each pixel value is handled as one byte symbol (0/1).
- gray_4bit: image is converted to grayscale and quantized to 16 levels; stored as true 4-bit indexed grayscale BMP.
- palette_8bit: original RGB image is quantized with adaptive 256-color palette and stored as 8-bit indexed BMP.

## Repository Structure

- [src/rle_image_compression](src/rle_image_compression): core package
- [src/rle_image_compression/bmp_codec.py](src/rle_image_compression/bmp_codec.py): indexed BMP read/write and reconstruction
- [src/rle_image_compression/scans.py](src/rle_image_compression/scans.py): row/column/64x64-zigzag flatten and inverse operations
- [src/rle_image_compression/rle_codec.py](src/rle_image_compression/rle_codec.py): hybrid RLE encode/decode and metrics
- [src/rle_image_compression/image_generator.py](src/rle_image_compression/image_generator.py): synthetic rocket scene generator
- [src/rle_image_compression/dataset.py](src/rle_image_compression/dataset.py): quantization into 1/4/8-bit variants
- [src/rle_image_compression/pipeline.py](src/rle_image_compression/pipeline.py): end-to-end benchmark and report generation
- [scripts/generate_dataset.py](scripts/generate_dataset.py): generate source image(s)
- [scripts/run_pipeline.py](scripts/run_pipeline.py): run full benchmark

Generated outputs:

- [images/generated_sources](images/generated_sources)
- [images/bmp](images/bmp)
- [images/decompressed](images/decompressed)
- [images/pixel_values](images/pixel_values)
- [encoded](encoded)
- [results](results)

generated_sources behavior:

- If no external input is given, this folder contains the synthetic source image created by the generator.
- If an external input is given, this folder contains the padded 512x512 preview of that external image in original color (RGB).
- Quantization to bw_1bit / gray_4bit / palette_8bit happens after this stage during benchmark processing.

## How to Run

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Generate dataset source image:

```bash
python scripts/generate_dataset.py
```

3. Run benchmark pipeline:

```bash
python scripts/run_pipeline.py
```

4. Run benchmark for an external image (example: rocket.png):

```bash
python scripts/run_pipeline.py --input-image rocket.png
```

5. Run benchmark on popular skimage samples (astronaut, coffee, chelsea, rocket, camera):

```bash
python scripts/run_skimage_benchmark.py
```

External input behavior:

- Input image is converted to grayscale.
- Aspect ratio is preserved.
- Image is resized to fit inside 512x512.
- Remaining area is padded (letterbox) to exactly 512x512.
- Processed preview is saved under images/generated_sources as external_<name>_512.png.

## Produced Result Files

Main benchmark tables:

- [results/compression_results.csv](results/compression_results.csv)
- [results/compression_results.json](results/compression_results.json)

Multi-image skimage summary:

- [results/skimage_benchmark_summary.csv](results/skimage_benchmark_summary.csv)
- [results/skimage_benchmark_summary.json](results/skimage_benchmark_summary.json)

64x64 scan-mode block analysis:

- [results/block64_results.csv](results/block64_results.csv)
- [results/block64_results.json](results/block64_results.json)
- [results/block64_scan_mode_comparison.csv](results/block64_scan_mode_comparison.csv)
- [results/block64_scan_mode_comparison.json](results/block64_scan_mode_comparison.json)
- [results/block64_scan_features.csv](results/block64_scan_features.csv)
- [results/block64_scan_features.json](results/block64_scan_features.json)

Local-only reports (ignored by git):

- results/REPORT.md

## Latest Result Summary

Summary below reflects the latest pipeline run (current scene: external_rocket_512):

| BMP Type | row_major (%) | col_major (%) | zigzag_64 (%) | Best |
|---|---:|---:|---:|---|
| bw_1bit | -1.04 | 1.27 | -21.97 | col_major |
| gray_4bit | 39.02 | 41.52 | 40.11 | col_major |
| palette_8bit | 55.54 | 56.09 | 53.38 | col_major |

Block-level scan winner counts (64x64):

| Winner Scan | Blocks |
|---|---:|
| row_major | 15 |
| col_major | 17 |
| zigzag_64 | 32 |

Detailed local analysis remains in results/REPORT.md.

## Technical Notes

- Header embedding is implemented in [src/rle_image_compression/pipeline.py](src/rle_image_compression/pipeline.py) inside _encode_file with meta + original BMP header + RLE payload layout.
- Zigzag is block-local (64x64), not global-image zigzag.
- Lossless validation is executed for every BMP type and scan mode combination during pipeline run.
