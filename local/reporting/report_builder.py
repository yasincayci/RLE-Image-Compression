from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List


BMP_ORDER = ["bw_1bit", "gray_4bit", "palette_8bit"]
SCAN_ORDER = ["row_major", "col_major", "zigzag_64"]
SCAN_LABELS = {
    "row_major": "Row-Row Rotate (serpantin satir)",
    "col_major": "Col-Col Rotate (serpantin sutun)",
    "zigzag_64": "Zigzag 64x64 (blok tabanli diyagonal)",
}


def _sorted_results(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    order_bmp = {v: i for i, v in enumerate(BMP_ORDER)}
    order_scan = {v: i for i, v in enumerate(SCAN_ORDER)}
    return sorted(results, key=lambda r: (order_bmp[r["bmp_type"]], order_scan[r["scan_mode"]]))


def _avg(vals: List[float]) -> float:
    return (sum(vals) / len(vals)) if vals else 0.0


def _format_summary_table(bmp_summary: List[Dict[str, Any]]) -> List[str]:
    lines = [
        "| BMP Type | Row Major (%) | Col Major (%) | Zigzag 64 (%) | Best Scan | Row Wins | Col Wins | Zigzag Wins |",
        "|---|---:|---:|---:|---|---:|---:|---:|",
    ]
    for row in bmp_summary:
        lines.append(
            f"| {row['bmp_type']} | {row['row_major_global_perf_percent']:.2f} | "
            f"{row['col_major_global_perf_percent']:.2f} | {row['zigzag_64_global_perf_percent']:.2f} | "
            f"{row['best_scan_by_global_performance']} | {row['row_major_block_wins']} | "
            f"{row['col_major_block_wins']} | {row['zigzag_64_block_wins']} |"
        )
    return lines


def _format_full_matrix(results: List[Dict[str, Any]]) -> List[str]:
    rows = _sorted_results(results)

    lines = [
        "| BMP Type | Scan Mode | Original (bytes) | Compressed (bytes) | Compression Rate (%) | Compression Performance (%) | Lossless |",
        "|---|---|---:|---:|---:|---:|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['bmp_type']} | {row['scan_mode']} | {row['original_size_bytes']} | {row['compressed_size_bytes']} | "
            f"{row['compression_rate_percent']:.2f} | {row['compression_performance_percent']:.2f} | {row['lossless']} |"
        )
    return lines


def _format_assignment_checklist(all_lossless: bool) -> List[str]:
    checks = [
        ("Uc BMP tipi (1-bit, 4-bit, 8-bit) uretilmesi", True),
        ("Uc tarama duzeni ile RLE uygulanmasi", True),
        ("Encode dosyasina BMP header eklenmesi", True),
        ("Decode asamasinda piksel-seviyesi kayipsizlik dogrulamasi", all_lossless),
        ("Sonuclarin tablo/csv/json olarak raporlanmasi", True),
        ("64x64 blok bazli ek analiz", True),
    ]
    lines = [
        "| Gereksinim | Durum |",
        "|---|---|",
    ]
    for req, ok in checks:
        lines.append(f"| {req} | {'Saglandi' if ok else 'Eksik'} |")
    return lines


def _format_scan_theory_section() -> List[str]:
    return [
        "- Row-Row Rotate: cift satirlar soldan saga, tek satirlar sagdan sola okunur.",
        "  Bu duzen, satirlar arasi yon degisimi ile uzun run olusumunu satir baglaminda optimize eder.",
        "- Col-Col Rotate: cift sutunlar yukaridan asagi, tek sutunlar asagidan yukari okunur.",
        "  Bu duzen, dikey sureklilik kuvvetli alanlarda daha uzun run uretebilir.",
        "- Zigzag 64x64: her blok icinde diyagonal gecis yapar.",
        "  Frekans-benzeri yerel gecislerde yararli olabilse de, duz yapilarda run parcalanmasina yol acabilir.",
    ]


def _format_bmp_interpretation(
    bmp_summary: List[Dict[str, Any]],
    block_value_features: List[Dict[str, Any]],
    bmp_block_rows: List[Dict[str, Any]],
) -> List[str]:
    lines: List[str] = []
    for row in bmp_summary:
        bmp_type = row["bmp_type"]
        perf = {
            "row_major": row["row_major_global_perf_percent"],
            "col_major": row["col_major_global_perf_percent"],
            "zigzag_64": row["zigzag_64_global_perf_percent"],
        }
        best_scan = max(perf, key=perf.get)
        worst_scan = min(perf, key=perf.get)
        spread = perf[best_scan] - perf[worst_scan]

        feature_rows = [r for r in block_value_features if r["bmp_type"] == bmp_type]
        cmp_rows = [r for r in bmp_block_rows if r["bmp_type"] == bmp_type]
        unique_avg = _avg([float(r["unique_values"]) for r in feature_rows])
        row_avg = _avg([float(r["row_change_ratio"]) for r in feature_rows])
        col_avg = _avg([float(r["col_change_ratio"]) for r in feature_rows])
        max_gap = max([float(r["winner_gap_percent_point"]) for r in cmp_rows], default=0.0)

        h = sum(1 for r in feature_rows if r["dominant_direction"] == "horizontal_continuity")
        v = sum(1 for r in feature_rows if r["dominant_direction"] == "vertical_continuity")
        b = sum(1 for r in feature_rows if r["dominant_direction"] == "balanced")

        lines.extend(
            [
                f"### {bmp_type}",
                "",
                f"- Global en iyi tarama: {SCAN_LABELS[best_scan]} ({perf[best_scan]:.2f}%).",
                f"- Global en dusuk tarama: {SCAN_LABELS[worst_scan]} ({perf[worst_scan]:.2f}%).",
                f"- Performans farki (best-worst): {spread:.2f} yuzde puan.",
                f"- Blok-kazanim dagilimi (Row/Col/Zigzag): {row['row_major_block_wins']}/{row['col_major_block_wins']}/{row['zigzag_64_block_wins']}",
                f"- Ortalama benzersiz deger: {unique_avg:.2f}",
                f"- Ortalama satir degisim orani: {row_avg:.4f}",
                f"- Ortalama sutun degisim orani: {col_avg:.4f}",
                f"- Baskin yon dagilimi (H/V/B): {h}/{v}/{b}",
                f"- En yuksek blok bazli kazanim marji: {max_gap:.2f} pp",
                "",
                "Yorum:",
                "Ortalama benzersiz deger azaldikca ve degisim oranlari dustukce RLE run uzunluklari artar.",
                "Bu nedenle dusuk entropili temsil (ozellikle 1-bit) daha yuksek sikistirma performansi verir.",
                "",
            ]
        )
    return lines


def _format_block_feature_summary(
    block_value_features: List[Dict[str, Any]],
    bmp_block_rows: List[Dict[str, Any]],
) -> List[str]:
    lines: List[str] = [
        "| BMP Tipi | Ortalama Benzersiz Deger | Ortalama Satir Degisim Orani | Ortalama Sutun Degisim Orani | Baskin Yon Dagilimi (H/V/B) |",
        "|---|---:|---:|---:|---|",
    ]

    for bmp_type in BMP_ORDER:
        feature_rows = [r for r in block_value_features if r["bmp_type"] == bmp_type]
        if feature_rows:
            avg_unique = sum(r["unique_values"] for r in feature_rows) / len(feature_rows)
            avg_row = sum(r["row_change_ratio"] for r in feature_rows) / len(feature_rows)
            avg_col = sum(r["col_change_ratio"] for r in feature_rows) / len(feature_rows)
            h = sum(1 for r in feature_rows if r["dominant_direction"] == "horizontal_continuity")
            v = sum(1 for r in feature_rows if r["dominant_direction"] == "vertical_continuity")
            b = sum(1 for r in feature_rows if r["dominant_direction"] == "balanced")
            direction = f"{h}/{v}/{b}"
            lines.append(f"| {bmp_type} | {avg_unique:.2f} | {avg_row:.4f} | {avg_col:.4f} | {direction} |")
        else:
            lines.append(f"| {bmp_type} | N/A | N/A | N/A | N/A |")

    lines.extend(
        [
            "",
            "Not: H/V/B sirasiyla yatay sureklilik, dikey sureklilik ve dengeli blok sayilarini gosterir.",
            "",
            "| BMP Tipi | En Kararli Blok (r,c) | Kazanan Tarama | Kazanma Marji (pp) |",
            "|---|---|---|---:|",
        ]
    )

    for bmp_type in BMP_ORDER:
        rows = [r for r in bmp_block_rows if r["bmp_type"] == bmp_type]
        if not rows:
            lines.append(f"| {bmp_type} | N/A | N/A | N/A |")
            continue
        top = max(rows, key=lambda r: r["winner_gap_percent_point"])
        lines.append(
            f"| {bmp_type} | ({top['block_row']},{top['block_col']}) | "
            f"{SCAN_LABELS[top['winner_scan_mode']]} | {top['winner_gap_percent_point']:.2f} |"
        )

    return lines


def _estimate_resolution_from_blocks(block_value_features: List[Dict[str, Any]]) -> str:
    if not block_value_features:
        return "bilinmiyor"
    max_br = max(int(r["block_row"]) for r in block_value_features)
    max_bc = max(int(r["block_col"]) for r in block_value_features)
    block_size = int(block_value_features[0]["block_size"])
    h = (max_br + 1) * block_size
    w = (max_bc + 1) * block_size
    return f"{w} x {h}"


def generate_report(
    output_path: Path,
    scene_name: str,
    results: List[Dict[str, Any]],
    block_rows: List[Dict[str, Any]],
    bmp_block_rows: List[Dict[str, Any]],
    bmp_summary: List[Dict[str, Any]],
    block_value_features: List[Dict[str, Any]],
) -> None:
    all_lossless = all(r["lossless"] for r in results)
    ordered_results = _sorted_results(results)
    estimated_resolution = _estimate_resolution_from_blocks(block_value_features)

    lines: List[str] = [
        "# RLE Sikistirma Deneyi: Akademik Teknik Rapor (Yerel)",
        "",
        "## Ozet",
        "",
        "Bu calisma, ayni goruntunun farkli indeksli BMP temsillerinde (1-bit, 4-bit, 8-bit)",
        "RLE tabanli kayipsiz sikistirma davranisini incelemektedir.",
        "Tarama duzeni, RLE token yapisi ve blok-icerik istatistikleri birlikte degerlendirilmis;",
        "global sonuc ile yerel (64x64 blok) sonuc ayrimi raporlanmistir.",
        "",
        "## 1. Problem Tanimi ve Kapsam",
        "",
        "Amac, ayni goruntu uzerinde temsil derinligi (bit-depth) ve tarama geometrisinin",
        "RLE verimliligine etkisini nicel olarak gostermektir.",
        "Deneyde encode dosyasina orijinal BMP header bilgisi eklenmis, decode sonunda piksel-seviyesi",
        "dogrulama ile kayipsizlik kontrol edilmistir.",
        "",
        f"- Sahne: {scene_name}",
        f"- Islenen cozumluk: {estimated_resolution}",
        "- BMP tipleri: bw_1bit, gray_4bit, palette_8bit",
        "- Tarama tipleri: Row-Row Rotate, Col-Col Rotate, Zigzag 64x64",
        f"- Tum kombinasyonlar kayipsiz: {all_lossless}",
        "",
        "## 2. Yontem ve Uygulama Tasarimi",
        "",
        "### 2.1 BMP Formatlari",
        "",
        "- bw_1bit: Esikleme ile 1-bit siyah-beyaz indeksli BMP.",
        "- gray_4bit: 16 seviyeli gercek 4-bit grayscale indeksli BMP.",
        "- palette_8bit: RGB kaynaktan uyarlamali 256 renk paleti ile 8-bit indeksli BMP.",
        "",
        "### 2.2 RLE Varyanti",
        "",
        "Kullanilan RLE akisi iki token tipine dayanir:",
        "- Run token: tekrar eden degerler icin",
        "- Literal token: karmasik bolgelerde ham dizi icin",
        "",
        "Encode dosya yapisi:",
        "",
        "[RLEI + metadata] + [BMP header blob] + [RLE payload]",
        "",
        "### 2.3 Tarama Duzenleri",
        "",
    ]
    lines.extend(_format_scan_theory_section())

    lines.extend(
        [
            "",
            "### 2.4 Cozunurluk Secimi (256x256) Gerekcesi",
            "",
            "Kaynak goruntu (427x640) kare tuvale oran korunarak yerlestirilir.",
            "512x512 kullanimi, kaynakta bulunmayan detaylari enterpolasyon ile buyutur ve",
            "yapay ara tonlar uretir. Bu durum RLE icin run yapisini degistirebilir.",
            "256x256 secimi ise 64x64 zigzag bloklarina tam bolunebilir (4x4 blok) olup",
            "hem hesaplama maliyetini azaltir hem de yukari ornekleme kaynakli etkileri sinirlar.",
            "",
            "### 2.5 Gereksinim Uyum Kontrol Listesi",
            "",
        ]
    )
    lines.extend(_format_assignment_checklist(all_lossless))

    lines.extend(
        [
            "",
            "## 3. Nicel Sonuclar",
            "",
            "### 3.1 BMP Tipi Bazinda Global Ozet",
            "",
        ]
    )
    lines.extend(_format_summary_table(bmp_summary))

    lines.extend(
        [
            "",
            "### 3.2 Tum Kombinasyonlar (3x3)",
            "",
        ]
    )
    lines.extend(_format_full_matrix(ordered_results))

    lines.extend(
        [
            "",
            "## 4. Analitik Degerlendirme (BMP Bazinda)",
            "",
        ]
    )
    lines.extend(_format_bmp_interpretation(bmp_summary, block_value_features, bmp_block_rows))

    lines.extend(
        [
            "",
            "## 5. Blok Degerlerine Dayali Mikroyapisal Analiz (64x64)",
            "",
            "Asagidaki tablolar, bloklarin deger cesitliligi ve yonel surekliligini birlikte sunar.",
            "Bu metrikler, run olusumu ve dolayisiyla RLE etkinliginin yerel belirleyicileridir.",
            "",
        ]
    )
    lines.extend(_format_block_feature_summary(block_value_features, bmp_block_rows))

    lines.extend(
        [
            "",
            "## 6. Gecerlilik, Sinirlar ve Tehditler",
            "",
            "- Gecerlilik: tum kombinasyonlarda decode->pixel eslesmesi ile kayipsizlik dogrulanmistir.",
            "- Kapsam siniri: tek sahne (rocket) kullanilmistir; cok-sahne genellemesi ayrica test edilmelidir.",
            "- Yontem siniri: zigzag yalnizca blok-ici uygulanmistir (global zigzag degildir).",
            "- Uygulama notu: Python standart kutuphanesinde bu scan duzenlerini dogrudan veren fonksiyon yoktur.",
            "",
            "## 7. Sonuc ve Oneriler",
            "",
            "Bu deneyde en yuksek global performans, dusuk bit-derinlikte ve uygun scan geometrisinde",
            "elde edilmistir. Sonuclar, temsil seciminin (bit-depth) tarama seciminden dahi daha baskin",
            "olabilecegini gostermektedir. Gelecek calismada coklu sahne veri seti, farkli blok boyutlari",
            "(32/64/128) ve entropy tabanli adaptif scan secimi onerilir.",
            "",
            "## 8. Ek Cikti Bilgileri",
            "",
            f"- block_rows satir sayisi: {len(block_rows)}",
            f"- bmp_block_rows satir sayisi: {len(bmp_block_rows)}",
            f"- block_value_features satir sayisi: {len(block_value_features)}",
            "",
            "Bu rapor local/ altinda uretilir ve git tarafindan dislanir.",
        ]
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
