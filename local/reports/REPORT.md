# RLE Sikistirma Deneyi: Akademik Teknik Rapor (Yerel)

## Ozet

Bu calisma, ayni goruntunun farkli indeksli BMP temsillerinde (1-bit, 4-bit, 8-bit)
RLE tabanli kayipsiz sikistirma davranisini incelemektedir.
Tarama duzeni, RLE token yapisi ve blok-icerik istatistikleri birlikte degerlendirilmis;
global sonuc ile yerel (64x64 blok) sonuc ayrimi raporlanmistir.

## 1. Problem Tanimi ve Kapsam

Amac, ayni goruntu uzerinde temsil derinligi (bit-depth) ve tarama geometrisinin
RLE verimliligine etkisini nicel olarak gostermektir.
Deneyde encode dosyasina orijinal BMP header bilgisi eklenmis, decode sonunda piksel-seviyesi
dogrulama ile kayipsizlik kontrol edilmistir.

- Sahne: skimage_rocket
- Islenen cozumluk: 256 x 256
- BMP tipleri: bw_1bit, gray_4bit, palette_8bit
- Tarama tipleri: Row-Row Rotate, Col-Col Rotate, Zigzag 64x64
- Tum kombinasyonlar kayipsiz: True

## 2. Yontem ve Uygulama Tasarimi

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

- Row-Row Rotate: cift satirlar soldan saga, tek satirlar sagdan sola okunur.
  Bu duzen, satirlar arasi yon degisimi ile uzun run olusumunu satir baglaminda optimize eder.
- Col-Col Rotate: cift sutunlar yukaridan asagi, tek sutunlar asagidan yukari okunur.
  Bu duzen, dikey sureklilik kuvvetli alanlarda daha uzun run uretebilir.
- Zigzag 64x64: her blok icinde diyagonal gecis yapar.
  Frekans-benzeri yerel gecislerde yararli olabilse de, duz yapilarda run parcalanmasina yol acabilir.

### 2.4 Cozunurluk Secimi (256x256) Gerekcesi

Kaynak goruntu (427x640) kare tuvale oran korunarak yerlestirilir.
512x512 kullanimi, kaynakta bulunmayan detaylari enterpolasyon ile buyutur ve
yapay ara tonlar uretir. Bu durum RLE icin run yapisini degistirebilir.
256x256 secimi ise 64x64 zigzag bloklarina tam bolunebilir (4x4 blok) olup
hem hesaplama maliyetini azaltir hem de yukari ornekleme kaynakli etkileri sinirlar.

### 2.5 Gereksinim Uyum Kontrol Listesi

| Gereksinim | Durum |
|---|---|
| Uc BMP tipi (1-bit, 4-bit, 8-bit) uretilmesi | Saglandi |
| Uc tarama duzeni ile RLE uygulanmasi | Saglandi |
| Encode dosyasina BMP header eklenmesi | Saglandi |
| Decode asamasinda piksel-seviyesi kayipsizlik dogrulamasi | Saglandi |
| Sonuclarin tablo/csv/json olarak raporlanmasi | Saglandi |
| 64x64 blok bazli ek analiz | Saglandi |

## 3. Nicel Sonuclar

### 3.1 BMP Tipi Bazinda Global Ozet

| BMP Type | Row Major (%) | Col Major (%) | Zigzag 64 (%) | Best Scan | Row Wins | Col Wins | Zigzag Wins |
|---|---:|---:|---:|---|---:|---:|---:|
| bw_1bit | 76.19 | 80.05 | 68.89 | col_major | 11 | 5 | 0 |
| gray_4bit | 37.90 | 39.94 | 26.13 | col_major | 7 | 9 | 0 |
| palette_8bit | 29.26 | 21.11 | 18.62 | row_major | 13 | 2 | 1 |

### 3.2 Tum Kombinasyonlar (3x3)

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

## 4. Analitik Degerlendirme (BMP Bazinda)

### bw_1bit

- Global en iyi tarama: Col-Col Rotate (serpantin sutun) (80.05%).
- Global en dusuk tarama: Zigzag 64x64 (blok tabanli diyagonal) (68.89%).
- Performans farki (best-worst): 11.16 yuzde puan.
- Blok-kazanim dagilimi (Row/Col/Zigzag): 11/5/0
- Ortalama benzersiz deger: 1.56
- Ortalama satir degisim orani: 0.0073
- Ortalama sutun degisim orani: 0.0066
- Baskin yon dagilimi (H/V/B): 2/2/12
- En yuksek blok bazli kazanim marji: 5.95 pp

Yorum:
Ortalama benzersiz deger azaldikca ve degisim oranlari dustukce RLE run uzunluklari artar.
Bu nedenle dusuk entropili temsil (ozellikle 1-bit) daha yuksek sikistirma performansi verir.

### gray_4bit

- Global en iyi tarama: Col-Col Rotate (serpantin sutun) (39.94%).
- Global en dusuk tarama: Zigzag 64x64 (blok tabanli diyagonal) (26.13%).
- Performans farki (best-worst): 13.81 yuzde puan.
- Blok-kazanim dagilimi (Row/Col/Zigzag): 7/9/0
- Ortalama benzersiz deger: 8.69
- Ortalama satir degisim orani: 0.1139
- Ortalama sutun degisim orani: 0.1006
- Baskin yon dagilimi (H/V/B): 6/7/3
- En yuksek blok bazli kazanim marji: 16.50 pp

Yorum:
Ortalama benzersiz deger azaldikca ve degisim oranlari dustukce RLE run uzunluklari artar.
Bu nedenle dusuk entropili temsil (ozellikle 1-bit) daha yuksek sikistirma performansi verir.

### palette_8bit

- Global en iyi tarama: Row-Row Rotate (serpantin satir) (29.26%).
- Global en dusuk tarama: Zigzag 64x64 (blok tabanli diyagonal) (18.62%).
- Performans farki (best-worst): 10.64 yuzde puan.
- Blok-kazanim dagilimi (Row/Col/Zigzag): 13/2/1
- Ortalama benzersiz deger: 86.19
- Ortalama satir degisim orani: 0.3462
- Ortalama sutun degisim orani: 0.3668
- Baskin yon dagilimi (H/V/B): 11/4/1
- En yuksek blok bazli kazanim marji: 19.44 pp

Yorum:
Ortalama benzersiz deger azaldikca ve degisim oranlari dustukce RLE run uzunluklari artar.
Bu nedenle dusuk entropili temsil (ozellikle 1-bit) daha yuksek sikistirma performansi verir.


## 5. Blok Degerlerine Dayali Mikroyapisal Analiz (64x64)

Asagidaki tablolar, bloklarin deger cesitliligi ve yonel surekliligini birlikte sunar.
Bu metrikler, run olusumu ve dolayisiyla RLE etkinliginin yerel belirleyicileridir.

| BMP Tipi | Ortalama Benzersiz Deger | Ortalama Satir Degisim Orani | Ortalama Sutun Degisim Orani | Baskin Yon Dagilimi (H/V/B) |
|---|---:|---:|---:|---|
| bw_1bit | 1.56 | 0.0073 | 0.0066 | 2/2/12 |
| gray_4bit | 8.69 | 0.1139 | 0.1006 | 6/7/3 |
| palette_8bit | 86.19 | 0.3462 | 0.3668 | 11/4/1 |

Not: H/V/B sirasiyla yatay sureklilik, dikey sureklilik ve dengeli blok sayilarini gosterir.

| BMP Tipi | En Kararli Blok (r,c) | Kazanan Tarama | Kazanma Marji (pp) |
|---|---|---|---:|
| bw_1bit | (2,2) | Col-Col Rotate (serpantin sutun) | 5.95 |
| gray_4bit | (2,2) | Col-Col Rotate (serpantin sutun) | 16.50 |
| palette_8bit | (2,0) | Row-Row Rotate (serpantin satir) | 19.44 |

## 6. Gecerlilik, Sinirlar ve Tehditler

- Gecerlilik: tum kombinasyonlarda decode->pixel eslesmesi ile kayipsizlik dogrulanmistir.
- Kapsam siniri: tek sahne (rocket) kullanilmistir; cok-sahne genellemesi ayrica test edilmelidir.
- Yontem siniri: zigzag yalnizca blok-ici uygulanmistir (global zigzag degildir).
- Uygulama notu: Python standart kutuphanesinde bu scan duzenlerini dogrudan veren fonksiyon yoktur.

## 7. Sonuc ve Oneriler

Bu deneyde en yuksek global performans, dusuk bit-derinlikte ve uygun scan geometrisinde
elde edilmistir. Sonuclar, temsil seciminin (bit-depth) tarama seciminden dahi daha baskin
olabilecegini gostermektedir. Gelecek calismada coklu sahne veri seti, farkli blok boyutlari
(32/64/128) ve entropy tabanli adaptif scan secimi onerilir.

## 8. Ek Cikti Bilgileri

- block_rows satir sayisi: 144
- bmp_block_rows satir sayisi: 48
- block_value_features satir sayisi: 48

Bu rapor local/ altinda uretilir ve git tarafindan dislanir.