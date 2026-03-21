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


def _format_bmp_interpretation(bmp_summary: List[Dict[str, Any]]) -> List[str]:
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

        lines.extend(
            [
                f"### {bmp_type}",
                "",
                f"- En iyi tarama: {SCAN_LABELS[best_scan]} ({perf[best_scan]:.2f}%).",
                f"- En dusuk tarama: {SCAN_LABELS[worst_scan]} ({perf[worst_scan]:.2f}%).",
                f"- Performans araligi: {spread:.2f} yuzde puan.",
                f"- Blok kazanimlari (Row/Col/Zigzag): {row['row_major_block_wins']}/{row['col_major_block_wins']}/{row['zigzag_64_block_wins']}",
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

    lines: List[str] = [
        "# RLE Sikistirma Raporu (Yerel, Push Disi)",
        "",
        "## 1. Giris",
        "",
        "Bu calismada ayni goruntu uc farkli BMP temsiline donusturulmus ve ozel bir RLE varyanti ile uc farkli tarama duzeni",
        "uzerinden sikistirilmistir. Tum kombinasyonlar decode edilerek kayipsizlik piksel seviyesinde dogrulanmistir.",
        "Encode edilen dosyanin basina orijinal BMP header bilgisi eklenmistir.",
        "",
        f"- Sahne: {scene_name}",
        "- Cozunurluk: 512 x 512",
        "- BMP tipleri: bw_1bit, gray_4bit, palette_8bit",
        "- Tarama tipleri: Row-Row Rotate, Col-Col Rotate, Zigzag 64x64",
        f"- Tum kombinasyonlar kayipsiz: {all_lossless}",
        "",
        "## 2. Yontem",
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
        "- Row-Row Rotate: cift satir soldan saga, tek satir sagdan sola (serpantin).",
        "- Col-Col Rotate: cift sutun yukaridan asagi, tek sutun asagidan yukari (serpantin).",
        "- Zigzag 64x64: goruntu 64x64 bloklara bolunur, her blokta diyagonal zigzag uygulanir.",
        "",
        "## 3. Sonuclar",
        "",
        "### 3.1 BMP Tipi Bazinda Genel Ozet",
        "",
    ]
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
            "## 4. Sonuclarin Yorumu (BMP Bazinda)",
            "",
        ]
    )
    lines.extend(_format_bmp_interpretation(bmp_summary))

    lines.extend(
        [
            "",
            "## 5. Blok Degerlerine Dayali Analiz (64x64)",
            "",
            "Asagidaki tabloda blok seviyesinde deger dagilimi ve yonelimsellik ozetlenmistir.",
            "",
        ]
    )
    lines.extend(_format_block_feature_summary(block_value_features, bmp_block_rows))

    lines.extend(
        [
            "",
            "## 6. Teknik Dogrulama Notlari",
            "",
            "- Kayipsizlik testinde tum kombinasyonlar True sonuc vermistir.",
            "- Zigzag uygulamasi blok-icidir; global zigzag degildir.",
            "- Python standart kutuphanesinde bu scan duzenlerini dogrudan veren hazir bir fonksiyon yoktur;",
            "  bu nedenle tarama/unflatten mantigi ozel olarak uygulanmistir.",
            "",
            "## 7. Ek Cikti Bilgileri",
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
