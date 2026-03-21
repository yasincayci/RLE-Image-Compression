# RLE Image Compression (BMP + Scan Modes)

Bu proje, tek bir 512x512 kaynak goruntu uzerinde 3 BMP turu ve 3 tarama modu ile kayipsiz RLE karsilastirmasi yapar.

- BMP turleri: `bw_1bit`, `gray_4bit`, `palette_8bit`
- Tarama modlari: `row_major`, `col_major`, `zigzag_64`
- Kayipsizlik: Her kombinasyonda decode sonrasi piksel dogrulamasi yapilir.

Varsayilan kaynak: `skimage` kutuphanesindeki roket goruntusu (`skimage_rocket`).
Opsiyonel olarak `--input-image` ile kendi goruntunuzu verebilirsiniz.

## Adim Adim Repo Yapisi

1. Calisan kod
- [src/rle_image_compression/bmp_codec.py](src/rle_image_compression/bmp_codec.py): indexed BMP yazma/okuma ve header tabanli yeniden olusturma
- [src/rle_image_compression/scans.py](src/rle_image_compression/scans.py): row/column/zigzag flatten-unflatten
- [src/rle_image_compression/rle_codec.py](src/rle_image_compression/rle_codec.py): hibrit RLE encode/decode
- [src/rle_image_compression/dataset.py](src/rle_image_compression/dataset.py): kaynak goruntuden 1/4/8-bit varyantlarin hazirlanmasi
- [src/rle_image_compression/pipeline.py](src/rle_image_compression/pipeline.py): tum benchmark akisi

2. Calistirma scripti
- [scripts/run_pipeline.py](scripts/run_pipeline.py): benchmarki tek komutla calistirir

3. Uretilen klasorler
- [images/generated_sources](images/generated_sources): 512x512 kaynak preview
- [images/bmp](images/bmp): BMP varyantlari
- [images/decompressed](images/decompressed): decode edilmis BMP ciktilari
- [images/pixel_values](images/pixel_values): piksel matris txt dosyalari
- [encoded](encoded): custom `.rle` dosyalari
- [results](results): sonuc tablolari

## Calistirma

```bash
pip install -r requirements.txt
python scripts/run_pipeline.py
```

Disaridan goruntu vermek icin:

```bash
python scripts/run_pipeline.py --input-image path/to/image.png
```

Not: Disaridan verilen goruntu oran korunarak 512x512 alana sigdirilir ve kalan alan pad edilir.

## Goruntu Donusum Ornekleri

Kaynak goruntu (varsayilan):

![skimage_rocket](images/generated_sources/skimage_rocket_512.png)

BMP turlerine donusum:

![bw_1bit](images/bmp/skimage_rocket_bw_1bit.bmp)
![gray_4bit](images/bmp/skimage_rocket_gray_4bit.bmp)
![palette_8bit](images/bmp/skimage_rocket_palette_8bit.bmp)

## Overall Sonuc

Son calistirmada olusan tablo:

- [results/compression_results.csv](results/compression_results.csv)
- [results/compression_results.json](results/compression_results.json)

Bu tabloda her BMP turu icin 3 scan modu yer alir ve en iyi sikistirma performansi dogrudan karsilastirilir.
