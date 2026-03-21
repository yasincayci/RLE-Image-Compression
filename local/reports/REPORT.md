# RLE Sikistirma Raporu (Yerel, Push Disi)

## 1. Giris

Bu calismada ayni goruntu uc farkli BMP temsiline donusturulmus ve ozel bir RLE varyanti ile uc farkli tarama duzeni
uzerinden sikistirilmistir. Tum kombinasyonlar decode edilerek kayipsizlik piksel seviyesinde dogrulanmistir.
Encode edilen dosyanin basina orijinal BMP header bilgisi eklenmistir.

- Sahne: skimage_rocket
- Cozunurluk: 512 x 512
- BMP tipleri: bw_1bit, gray_4bit, palette_8bit
- Tarama tipleri: Row-Row Rotate, Col-Col Rotate, Zigzag 64x64
- Tum kombinasyonlar kayipsiz: True

## 2. Yontem

### 2.1 BMP Formatlari

- bw_1bit: Esikleme ile 1-bit siyah-beyaz indeksli BMP.
- gray_4bit: 16 seviyeli gercek 4-bit grayscale indeksli BMP.
- palette_8bit: RGB kaynaktan uyarlamali 256 renk paleti ile 8-bit indeksli BMP.

### 2.2 RLE Varyanti

Kullanilan RLE akisi iki token tipine dayanir:
- Run token: tekrar eden degerler icin
- Literal token: karmasik bolgelerde ham dizi icin

Encode dosya yapisi:

[RLEI + metadata] + [BMP header blob] + [RLE payload]

### 2.3 Tarama Duzenleri

- Row-Row Rotate: cift satir soldan saga, tek satir sagdan sola (serpantin).
- Col-Col Rotate: cift sutun yukaridan asagi, tek sutun asagidan yukari (serpantin).
- Zigzag 64x64: goruntu 64x64 bloklara bolunur, her blokta diyagonal zigzag uygulanir.

## 3. Sonuclar

### 3.1 BMP Tipi Bazinda Genel Ozet

| BMP Type | Row Major (%) | Col Major (%) | Zigzag 64 (%) | Best Scan | Row Wins | Col Wins | Zigzag Wins |
|---|---:|---:|---:|---|---:|---:|---:|
| bw_1bit | 78.61 | 82.62 | 72.10 | col_major | 52 | 11 | 1 |
| gray_4bit | 44.43 | 46.34 | 35.82 | col_major | 40 | 24 | 0 |
| palette_8bit | 34.26 | 28.91 | 25.65 | row_major | 55 | 8 | 1 |

### 3.2 Tum Kombinasyonlar (3x3)

| BMP Type | Scan Mode | Original (bytes) | Compressed (bytes) | Compression Rate (%) | Compression Performance (%) | Lossless |
|---|---|---:|---:|---:|---:|---|
| bw_1bit | row_major | 32830 | 7022 | 21.39 | 78.61 | True |
| bw_1bit | col_major | 32830 | 5706 | 17.38 | 82.62 | True |
| bw_1bit | zigzag_64 | 32830 | 9161 | 27.90 | 72.10 | True |
| gray_4bit | row_major | 131190 | 72904 | 55.57 | 44.43 | True |
| gray_4bit | col_major | 131190 | 70397 | 53.66 | 46.34 | True |
| gray_4bit | zigzag_64 | 131190 | 84197 | 64.18 | 35.82 | True |
| palette_8bit | row_major | 263222 | 173033 | 65.74 | 34.26 | True |
| palette_8bit | col_major | 263222 | 187130 | 71.09 | 28.91 | True |
| palette_8bit | zigzag_64 | 263222 | 195702 | 74.35 | 25.65 | True |

## 4. Sonuclarin Yorumu (BMP Bazinda)

### bw_1bit

- En iyi tarama: Col-Col Rotate (serpantin sutun) (82.62%).
- En dusuk tarama: Zigzag 64x64 (blok tabanli diyagonal) (72.10%).
- Performans araligi: 10.52 yuzde puan.
- Blok kazanimlari (Row/Col/Zigzag): 52/11/1

### gray_4bit

- En iyi tarama: Col-Col Rotate (serpantin sutun) (46.34%).
- En dusuk tarama: Zigzag 64x64 (blok tabanli diyagonal) (35.82%).
- Performans araligi: 10.52 yuzde puan.
- Blok kazanimlari (Row/Col/Zigzag): 40/24/0

### palette_8bit

- En iyi tarama: Row-Row Rotate (serpantin satir) (34.26%).
- En dusuk tarama: Zigzag 64x64 (blok tabanli diyagonal) (25.65%).
- Performans araligi: 8.61 yuzde puan.
- Blok kazanimlari (Row/Col/Zigzag): 55/8/1


## 5. Blok Degerlerine Dayali Analiz (64x64)

Asagidaki tabloda blok seviyesinde deger dagilimi ve yonelimsellik ozetlenmistir.

| BMP Tipi | Ortalama Benzersiz Deger | Ortalama Satir Degisim Orani | Ortalama Sutun Degisim Orani | Baskin Yon Dagilimi (H/V/B) |
|---|---:|---:|---:|---|
| bw_1bit | 1.30 | 0.0070 | 0.0054 | 3/10/51 |
| gray_4bit | 5.62 | 0.1092 | 0.0961 | 15/26/23 |
| palette_8bit | 51.47 | 0.3170 | 0.3310 | 27/18/19 |

Not: H/V/B sirasiyla yatay sureklilik, dikey sureklilik ve dengeli blok sayilarini gosterir.

| BMP Tipi | En Kararli Blok (r,c) | Kazanan Tarama | Kazanma Marji (pp) |
|---|---|---|---:|
| bw_1bit | (4,4) | Col-Col Rotate (serpantin sutun) | 9.91 |
| gray_4bit | (5,4) | Col-Col Rotate (serpantin sutun) | 23.44 |
| palette_8bit | (1,3) | Row-Row Rotate (serpantin satir) | 28.56 |

## 6. Teknik Dogrulama Notlari

- Kayipsizlik testinde tum kombinasyonlar True sonuc vermistir.
- Zigzag uygulamasi blok-icidir; global zigzag degildir.
- Python standart kutuphanesinde bu scan duzenlerini dogrudan veren hazir bir fonksiyon yoktur;
  bu nedenle tarama/unflatten mantigi ozel olarak uygulanmistir.

## 7. Ek Cikti Bilgileri

- block_rows satir sayisi: 576
- bmp_block_rows satir sayisi: 192
- block_value_features satir sayisi: 192

Bu rapor local/ altinda uretilir ve git tarafindan dislanir.