#!/usr/bin/env python3
from __future__ import annotations

import csv
import html
import io
import json
import math
import urllib.request
from collections import OrderedDict
from datetime import date, datetime
from pathlib import Path
from statistics import mean


BASE_DIR = Path(__file__).resolve().parent
RAW_DIR = BASE_DIR / "data" / "raw"
PROCESSED_DIR = BASE_DIR / "data" / "processed"
ARTIFACT_DIR = BASE_DIR / "artifacts"
DRAFT_DIR = BASE_DIR / "drafts"

OI_MONTHLY_URL = (
    "https://raw.githubusercontent.com/OpportunityInsights/EconomicTracker/main/data/"
    "Affinity%20-%20National%20-%20Monthly.csv"
)
OI_SHARES_2020_URL = (
    "https://raw.githubusercontent.com/OpportunityInsights/EconomicTracker/main/data/"
    "Affinity%20Income%20Shares%20-%20National%20-%202020.csv"
)
OI_DOC_URL = (
    "https://raw.githubusercontent.com/OpportunityInsights/EconomicTracker/main/docs/"
    "oi_tracker_data_documentation.md"
)
OI_DICT_URL = (
    "https://raw.githubusercontent.com/OpportunityInsights/EconomicTracker/main/docs/"
    "oi_tracker_data_dictionary.md"
)

FRED_SERIES = OrderedDict(
    [
        ("general_merchandise", "MRTSSM452USN"),
        ("ecommerce", "MRTSSM4541USN"),
        ("grocery", "MRTSSM44511USN"),
        ("restaurants", "MRTSSM7225USN"),
        ("clothing", "MRTSSM4481USN"),
        ("furniture", "MRTSSM442USN"),
        ("sentiment", "UMCSENT"),
        ("cpi", "CPIAUCSL"),
    ]
)

FRED_LABELS = {
    "general_merchandise": "General Merchandise",
    "ecommerce": "E-commerce",
    "grocery": "Grocery",
    "restaurants": "Restaurants",
    "clothing": "Clothing",
    "furniture": "Furniture",
}

FRED_SOURCE_LINKS = {
    "general_merchandise": "https://fred.stlouisfed.org/series/MRTSSM452USN",
    "ecommerce": "https://fred.stlouisfed.org/series/MRTSSM4541USN",
    "grocery": "https://fred.stlouisfed.org/series/MRTSSM44511USN",
    "restaurants": "https://fred.stlouisfed.org/series/MRTSSM7225USN",
    "clothing": "https://fred.stlouisfed.org/series/MRTSSM4481USN",
    "furniture": "https://fred.stlouisfed.org/series/MRTSSM442USN",
    "sentiment": "https://fred.stlouisfed.org/series/UMCSENT",
    "cpi": "https://fred.stlouisfed.org/series/CPIAUCSL",
}

RETAIL_COLORS = OrderedDict(
    [
        ("ecommerce", "#0f766e"),
        ("restaurants", "#d97706"),
        ("grocery", "#15803d"),
        ("general_merchandise", "#2563eb"),
        ("clothing", "#9333ea"),
        ("furniture", "#dc2626"),
    ]
)

OI_CATEGORIES = OrderedDict(
    [
        ("all", ("All Spending", "spend_s_all")),
        ("grocery", ("Grocery", "spend_s_grf")),
        ("restaurants_hotels", ("Restaurants & Hotels", "spend_s_acf")),
        ("apparel", ("Apparel & Accessories", "spend_s_aap")),
        ("general_merchandise", ("General Merchandise", "spend_s_gen")),
        ("retail_no_grocery", ("Retail ex Grocery", "spend_s_retail_no_grocery")),
    ]
)

QUARTILE_LABELS = OrderedDict(
    [
        ("q1", "Q1 Low Income"),
        ("q2", "Q2"),
        ("q3", "Q3"),
        ("q4", "Q4 High Income"),
    ]
)

QUARTILE_COLORS = {
    "q1": "#0f766e",
    "q2": "#0284c7",
    "q3": "#7c3aed",
    "q4": "#dc2626",
}


def ensure_dirs() -> None:
    for path in (RAW_DIR, PROCESSED_DIR, ARTIFACT_DIR, DRAFT_DIR):
        path.mkdir(parents=True, exist_ok=True)


def fetch_to_path(url: str, path: Path) -> None:
    with urllib.request.urlopen(url, timeout=60) as response:
        path.write_bytes(response.read())


def month_date(year: int | str, month: int | str) -> date:
    return date(int(year), int(month), 1)


def format_month(value: date) -> str:
    return value.strftime("%B %Y")


def format_iso(value: date) -> str:
    return value.isoformat()


def parse_float(value: str) -> float | None:
    if value in {"", "."}:
        return None
    return float(value)


def load_fred_series(path: Path, series_id: str) -> dict[date, float]:
    rows = csv.DictReader(path.read_text(encoding="utf-8").splitlines())
    data: dict[date, float] = {}
    for row in rows:
        parsed = parse_float(row[series_id])
        if parsed is None:
            continue
        data[datetime.strptime(row["observation_date"], "%Y-%m-%d").date()] = parsed
    return data


def load_oi_monthly(path: Path) -> list[tuple[date, dict[str, str]]]:
    rows = csv.DictReader(path.read_text(encoding="utf-8").splitlines())
    records: list[tuple[date, dict[str, str]]] = []
    for row in rows:
        if row.get("freq") != "m":
            continue
        records.append((month_date(row["year"], row["month"]), row))
    records.sort(key=lambda item: item[0])
    return records


def load_income_shares(path: Path) -> dict[str, float]:
    rows = csv.DictReader(path.read_text(encoding="utf-8").splitlines())
    shares: dict[str, float] = {}
    for row in rows:
        shares[f"q{row['income_quartile']}"] = float(row["share_jan2020"])
    return shares


def previous_month_same_year(dates: list[date], current: date) -> date | None:
    target = date(current.year - 1, current.month, 1)
    return target if target in dates else None


def pearson(values_x: list[float], values_y: list[float]) -> float | None:
    if not values_x or len(values_x) != len(values_y):
        return None
    mean_x = mean(values_x)
    mean_y = mean(values_y)
    std_x = math.sqrt(mean((value - mean_x) ** 2 for value in values_x))
    std_y = math.sqrt(mean((value - mean_y) ** 2 for value in values_y))
    if std_x == 0 or std_y == 0:
        return None
    covariance = mean((x - mean_x) * (y - mean_y) for x, y in zip(values_x, values_y))
    return covariance / (std_x * std_y)


def interpolated_month_map(series: dict[date, float], full_dates: list[date]) -> dict[date, float]:
    filled = dict(series)
    for index, current in enumerate(full_dates):
        if current in filled:
            continue
        previous = next((full_dates[i] for i in range(index - 1, -1, -1) if full_dates[i] in filled), None)
        following = next((full_dates[i] for i in range(index + 1, len(full_dates)) if full_dates[i] in filled), None)
        if previous and following:
            filled[current] = (filled[previous] + filled[following]) / 2
    return filled


def nice_ceiling(value: float, step: int = 10) -> int:
    return int(math.ceil(value / step) * step)


def svg_text(x: float, y: float, value: str, *, size: int = 16, weight: int = 400, fill: str = "#1f2937", anchor: str = "start") -> str:
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" font-weight="{weight}" '
        f'fill="{fill}" text-anchor="{anchor}" font-family="Georgia, Times New Roman, serif">'
        f"{html.escape(value)}</text>"
    )


def interpolate_color(start_hex: str, end_hex: str, ratio: float) -> str:
    ratio = max(0.0, min(1.0, ratio))
    start = tuple(int(start_hex[i : i + 2], 16) for i in (1, 3, 5))
    end = tuple(int(end_hex[i : i + 2], 16) for i in (1, 3, 5))
    channels = [round(start[idx] + (end[idx] - start[idx]) * ratio) for idx in range(3)]
    return "#" + "".join(f"{channel:02x}" for channel in channels)


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build_line_chart(
    path: Path,
    dates: list[date],
    series_map: OrderedDict[str, list[float]],
    title: str,
    subtitle: str,
    baseline: float = 100.0,
) -> None:
    width = 1120
    height = 760
    margin_left = 100
    margin_right = 180
    margin_top = 120
    margin_bottom = 90
    plot_width = width - margin_left - margin_right
    plot_height = height - margin_top - margin_bottom

    values = [value for series in series_map.values() for value in series]
    y_min = min(70.0, math.floor(min(values) / 10) * 10)
    y_max = max(170.0, nice_ceiling(max(values), 10))

    def x_pos(index: int) -> float:
        if len(dates) == 1:
            return margin_left + plot_width / 2
        return margin_left + (index / (len(dates) - 1)) * plot_width

    def y_pos(value: float) -> float:
        return margin_top + plot_height - ((value - y_min) / (y_max - y_min)) * plot_height

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{html.escape(title)}">',
        '<rect width="100%" height="100%" fill="#f7f3eb"/>',
        '<rect x="32" y="32" width="1056" height="696" rx="28" fill="#fffdf9" stroke="#e8dcc7"/>',
        svg_text(84, 92, title, size=34, weight=700, fill="#111827"),
        svg_text(84, 124, subtitle, size=16, fill="#4b5563"),
    ]

    for tick in range(int(y_min), int(y_max) + 1, 10):
        y = y_pos(float(tick))
        stroke = "#d8d0c4" if tick == baseline else "#ebe5db"
        dash = ' stroke-dasharray="5 5"' if tick == baseline else ""
        parts.append(f'<line x1="{margin_left}" y1="{y:.1f}" x2="{margin_left + plot_width}" y2="{y:.1f}" stroke="{stroke}"{dash}/>')
        parts.append(svg_text(margin_left - 16, y + 5, str(tick), size=13, fill="#6b7280", anchor="end"))

    tick_indexes = [index for index, current in enumerate(dates) if current.month == 1]
    if tick_indexes[-1] != len(dates) - 1:
        tick_indexes.append(len(dates) - 1)
    for index in tick_indexes:
        x = x_pos(index)
        current = dates[index]
        parts.append(f'<line x1="{x:.1f}" y1="{margin_top}" x2="{x:.1f}" y2="{margin_top + plot_height}" stroke="#f0ebe2"/>')
        label = current.strftime("%Y") if current.month == 1 else current.strftime("%b %Y")
        parts.append(svg_text(x, margin_top + plot_height + 28, label, size=13, fill="#6b7280", anchor="middle"))

    for series_name, values_for_series in series_map.items():
        points = " ".join(f"{x_pos(index):.1f},{y_pos(value):.1f}" for index, value in enumerate(values_for_series))
        parts.append(
            f'<polyline fill="none" stroke="{RETAIL_COLORS[series_name]}" stroke-width="4" '
            f'stroke-linecap="round" stroke-linejoin="round" points="{points}"/>'
        )
        last_x = x_pos(len(values_for_series) - 1)
        last_y = y_pos(values_for_series[-1])
        parts.append(f'<circle cx="{last_x:.1f}" cy="{last_y:.1f}" r="5" fill="{RETAIL_COLORS[series_name]}"/>')
        parts.append(svg_text(last_x + 10, last_y + 5, FRED_LABELS[series_name], size=14, weight=600, fill=RETAIL_COLORS[series_name]))

    parts.extend(
        [
            svg_text(width - 170, 96, "Real sales index", size=15, weight=700, fill="#111827"),
            svg_text(width - 170, 120, "2019 average = 100", size=13, fill="#4b5563"),
        ]
    )

    parts.append("</svg>")
    path.write_text("\n".join(parts), encoding="utf-8")


def build_heatmap(
    path: Path,
    matrix: list[tuple[str, dict[str, float]]],
    title: str,
    subtitle: str,
) -> None:
    width = 1080
    height = 720
    margin_left = 270
    margin_top = 180
    cell_width = 150
    cell_height = 72
    max_value = max(value for _, values in matrix for value in values.values())
    min_value = min(value for _, values in matrix for value in values.values())

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{html.escape(title)}">',
        '<rect width="100%" height="100%" fill="#f7f3eb"/>',
        '<rect x="28" y="28" width="1024" height="664" rx="28" fill="#fffdf9" stroke="#e8dcc7"/>',
        svg_text(84, 94, title, size=34, weight=700, fill="#111827"),
        svg_text(84, 126, subtitle, size=16, fill="#4b5563"),
        svg_text(84, 154, "Values are seasonally adjusted percent change vs the January 2020 baseline.", size=14, fill="#6b7280"),
    ]

    for column_index, quartile in enumerate(QUARTILE_LABELS):
        x = margin_left + column_index * cell_width + cell_width / 2
        parts.append(svg_text(x, margin_top - 26, QUARTILE_LABELS[quartile], size=14, weight=700, fill="#1f2937", anchor="middle"))

    for row_index, (label, values) in enumerate(matrix):
        y = margin_top + row_index * cell_height
        parts.append(svg_text(84, y + 44, label, size=16, weight=600, fill="#1f2937"))
        for column_index, quartile in enumerate(QUARTILE_LABELS):
            x = margin_left + column_index * cell_width
            current = values[quartile]
            ratio = 0.5 if max_value == min_value else (current - min_value) / (max_value - min_value)
            fill = interpolate_color("#e8f5f2", "#0f766e", ratio)
            parts.append(
                f'<rect x="{x}" y="{y}" width="{cell_width - 8}" height="{cell_height - 8}" '
                f'rx="18" fill="{fill}" stroke="#d8ebe6"/>'
            )
            text_fill = "#ffffff" if ratio > 0.58 else "#0f172a"
            parts.append(svg_text(x + (cell_width - 8) / 2, y + 43, f"{current:.0f}%", size=18, weight=700, fill=text_fill, anchor="middle"))

    legend_y = 645
    parts.append(svg_text(84, legend_y, "Lower change", size=13, fill="#6b7280"))
    for step in range(6):
        x = 176 + step * 42
        parts.append(
            f'<rect x="{x}" y="{legend_y - 18}" width="36" height="16" rx="8" '
            f'fill="{interpolate_color("#e8f5f2", "#0f766e", step / 5)}"/>'
        )
    parts.append(svg_text(446, legend_y, "Higher change", size=13, fill="#6b7280"))
    parts.append("</svg>")
    path.write_text("\n".join(parts), encoding="utf-8")


def build_slope_chart(
    path: Path,
    baseline_shares: dict[str, float],
    latest_shares: dict[str, float],
    title: str,
    subtitle: str,
) -> None:
    width = 980
    height = 620
    left_x = 260
    right_x = 700
    top = 140
    bottom = 540
    y_min = 10
    y_max = 40

    def y_pos(value: float) -> float:
        return top + (y_max - value) / (y_max - y_min) * (bottom - top)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{html.escape(title)}">',
        '<rect width="100%" height="100%" fill="#f7f3eb"/>',
        '<rect x="24" y="24" width="932" height="572" rx="28" fill="#fffdf9" stroke="#e8dcc7"/>',
        svg_text(72, 88, title, size=30, weight=700, fill="#111827"),
        svg_text(72, 118, subtitle, size=15, fill="#4b5563"),
        svg_text(left_x, 136, "Jan 2020 baseline share", size=15, weight=700, fill="#111827", anchor="middle"),
        svg_text(right_x, 136, "Estimated latest share", size=15, weight=700, fill="#111827", anchor="middle"),
    ]

    for tick in range(y_min, y_max + 1, 5):
        y = y_pos(tick)
        parts.append(f'<line x1="120" y1="{y:.1f}" x2="840" y2="{y:.1f}" stroke="#efe8dc"/>')
        parts.append(svg_text(108, y + 5, f"{tick}%", size=12, fill="#6b7280", anchor="end"))

    for quartile in QUARTILE_LABELS:
        base = baseline_shares[quartile] * 100
        latest = latest_shares[quartile] * 100
        y1 = y_pos(base)
        y2 = y_pos(latest)
        color = QUARTILE_COLORS[quartile]
        parts.append(f'<line x1="{left_x}" y1="{y1:.1f}" x2="{right_x}" y2="{y2:.1f}" stroke="{color}" stroke-width="4"/>')
        parts.append(f'<circle cx="{left_x}" cy="{y1:.1f}" r="8" fill="{color}"/>')
        parts.append(f'<circle cx="{right_x}" cy="{y2:.1f}" r="8" fill="{color}"/>')
        parts.append(svg_text(left_x - 18, y1 + 5, f"{base:.1f}%", size=13, weight=600, fill=color, anchor="end"))
        parts.append(svg_text(right_x + 18, y2 + 5, f"{latest:.1f}%", size=13, weight=600, fill=color))
        parts.append(svg_text(left_x - 28, y1 - 10, QUARTILE_LABELS[quartile], size=13, weight=700, fill=color, anchor="end"))

    parts.append(svg_text(72, 572, "Latest shares are estimated by re-weighting Jan 2020 shares with the most recent all-spending index.", size=13, fill="#6b7280"))
    parts.append("</svg>")
    path.write_text("\n".join(parts), encoding="utf-8")


def build_cover(path: Path, title: str, subtitle: str, key_stats: list[str]) -> None:
    width = 1600
    height = 900
    stat_pairs = [item.split(":", 1) for item in key_stats]
    normalized_stats = [(label.strip(), value.strip()) for label, value in stat_pairs if len([label, value]) == 2]
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{html.escape(title)}">',
        """
        <defs>
          <linearGradient id="bg" x1="0" x2="1" y1="0" y2="1">
            <stop offset="0%" stop-color="#fbf6ea"/>
            <stop offset="55%" stop-color="#f6efe2"/>
            <stop offset="100%" stop-color="#edf8f5"/>
          </linearGradient>
          <linearGradient id="panel" x1="0" x2="1" y1="0" y2="1">
            <stop offset="0%" stop-color="#fffdfa"/>
            <stop offset="100%" stop-color="#f8fafc"/>
          </linearGradient>
          <linearGradient id="inkpanel" x1="0" x2="1" y1="0" y2="1">
            <stop offset="0%" stop-color="#172033"/>
            <stop offset="100%" stop-color="#0f172a"/>
          </linearGradient>
          <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
            <feDropShadow dx="0" dy="18" stdDeviation="24" flood-color="#1f2937" flood-opacity="0.12"/>
          </filter>
        </defs>
        """.strip(),
        '<rect width="100%" height="100%" fill="url(#bg)"/>',
        '<circle cx="1350" cy="150" r="260" fill="#f7d774" opacity="0.20"/>',
        '<circle cx="112" cy="824" r="240" fill="#8fd0df" opacity="0.18"/>',
        '<path d="M1140 0 L1600 0 L1600 390 Q1450 360 1345 295 Q1228 220 1140 0 Z" fill="#f0dcb8" opacity="0.48"/>',
        '<rect x="70" y="66" width="1460" height="768" rx="40" fill="url(#panel)" stroke="#eadcc7" filter="url(#shadow)"/>',
        '<rect x="110" y="116" width="660" height="668" rx="34" fill="url(#inkpanel)"/>',
        '<rect x="842" y="132" width="626" height="310" rx="30" fill="#f8fbfd" stroke="#d9e6eb"/>',
        '<rect x="842" y="472" width="300" height="276" rx="28" fill="#fff8ee" stroke="#eedcbb"/>',
        '<rect x="1166" y="472" width="302" height="276" rx="28" fill="#f6fbfa" stroke="#cfe7e1"/>',
        '<rect x="690" y="438" width="182" height="118" rx="24" fill="#fff7df" stroke="#eccc7d" filter="url(#shadow)"/>',
        svg_text(160, 174, "Consumer Analytics Project", size=22, weight=700, fill="#80d9cf"),
        svg_text(160, 256, title, size=64, weight=700, fill="#f8fbff"),
        svg_text(160, 312, "Where spending is holding up by category", size=28, weight=600, fill="#c9d4e6"),
        svg_text(160, 350, "and income segment", size=28, weight=600, fill="#c9d4e6"),
        svg_text(160, 410, subtitle, size=22, fill="#d5dfec"),
    ]

    stat_card_y = 502
    stat_card_x = 160
    stat_card_w = 260
    stat_card_h = 112
    stat_gap = 26
    for index, (label, value) in enumerate(normalized_stats[:3]):
        x = stat_card_x + index * (stat_card_w + stat_gap)
        parts.append(f'<rect x="{x}" y="{stat_card_y}" width="{stat_card_w}" height="{stat_card_h}" rx="24" fill="#fff8e7" opacity="0.98" stroke="#f0d799"/>')
        parts.append(svg_text(x + 24, stat_card_y + 42, label, size=17, weight=700, fill="#8a5a16"))
        parts.append(svg_text(x + 24, stat_card_y + 82, value, size=24, weight=700, fill="#10223f"))

    parts.extend(
        [
            svg_text(160, 676, "Why this matters", size=18, weight=700, fill="#80d9cf"),
            svg_text(160, 712, "This piece combines public spending, retail, and", size=20, fill="#d5dfec"),
            svg_text(160, 742, "consumer sentiment signals into a decision-ready", size=20, fill="#d5dfec"),
            svg_text(160, 772, "view of resilience, pressure, and customer mix.", size=20, fill="#d5dfec"),
        ]
    )

    chart_left = 872
    chart_top = 156
    chart_points = {
        "#0f766e": [(0, 208), (58, 178), (118, 170), (178, 136), (236, 144), (296, 112), (354, 104), (412, 76), (470, 60), (530, 48)],
        "#d97706": [(0, 226), (58, 220), (118, 194), (178, 178), (236, 168), (296, 154), (354, 148), (412, 132), (470, 136), (530, 126)],
        "#dc2626": [(0, 208), (58, 158), (118, 154), (178, 146), (236, 160), (296, 154), (354, 166), (412, 178), (470, 196), (530, 208)],
        "#2563eb": [(0, 214), (58, 208), (118, 210), (178, 202), (236, 194), (296, 188), (354, 180), (412, 174), (470, 176), (530, 172)],
    }
    for tick_y in (226, 186, 146, 106, 66):
        parts.append(f'<line x1="{chart_left + 20}" y1="{chart_top + tick_y}" x2="{chart_left + 560}" y2="{chart_top + tick_y}" stroke="#e9eef2"/>')
    for tick_x, label in zip((0, 110, 220, 330, 440, 530), ("2019", "2020", "2021", "2022", "2024", "2026")):
        x = chart_left + 22 + tick_x
        parts.append(f'<line x1="{x}" y1="{chart_top + 36}" x2="{x}" y2="{chart_top + 258}" stroke="#f1f5f9"/>')
        parts.append(svg_text(x, chart_top + 286, label, size=13, fill="#64748b", anchor="middle"))
    parts.append(svg_text(876, 188, "Real Demand by Category", size=28, weight=700, fill="#0f172a"))
    parts.append(svg_text(876, 218, "2019 real-sales baseline indexed to 100", size=16, fill="#5b6577"))
    for color, points in chart_points.items():
        shifted = " ".join(f"{chart_left + 22 + x},{chart_top + 42 + y}" for x, y in points)
        parts.append(f'<polyline fill="none" stroke="{color}" stroke-width="8" stroke-linecap="round" stroke-linejoin="round" points="{shifted}"/>')
    legend_items = [
        ("E-commerce", "#0f766e"),
        ("Restaurants", "#d97706"),
        ("Furniture", "#dc2626"),
        ("Grocery", "#2563eb"),
    ]
    for index, (label, color) in enumerate(legend_items):
        lx = 878 + index * 142
        ly = 406
        parts.append(f'<rect x="{lx}" y="{ly}" width="18" height="18" rx="9" fill="{color}"/>')
        parts.append(svg_text(lx + 28, ly + 14, label, size=14, weight=600, fill="#334155"))

    heat_y = 540
    cell_w = 64
    cell_h = 48
    sample_rows = [
        ("All Spend", [48, 42, 37, 29]),
        ("Grocery", [20, 18, 18, 19]),
        ("Gen Merch", [110, 112, 97, 74]),
    ]
    parts.append(svg_text(876, 508, "Latest Income Snapshot", size=24, weight=700, fill="#0f172a"))
    parts.append(svg_text(876, 534, "March 2026 vs Jan 2020 baseline", size=15, fill="#5b6577"))
    for idx, quartile in enumerate(QUARTILE_LABELS):
        parts.append(svg_text(1240 + idx * cell_w, heat_y - 18, quartile.upper(), size=13, weight=700, fill="#475569", anchor="middle"))
    for row_index, (row_label, row_values) in enumerate(sample_rows):
        y = heat_y + row_index * 64
        parts.append(svg_text(878, y + 32, row_label, size=16, weight=600, fill="#1f2937"))
        for col_index, row_value in enumerate(row_values):
            fill = interpolate_color("#e8f5f2", "#0f766e", min(row_value / 115, 1))
            x = 1208 + col_index * cell_w
            text_fill = "#ffffff" if row_value > 55 else "#0f172a"
            parts.append(f'<rect x="{x}" y="{y}" width="{cell_w - 10}" height="{cell_h}" rx="16" fill="{fill}" stroke="#d8ebe6"/>')
            parts.append(svg_text(x + (cell_w - 10) / 2, y + 31, f"{row_value}%", size=16, weight=700, fill=text_fill, anchor="middle"))

    parts.append(svg_text(874, 708, "Q1 low-income ZIP codes are gaining faster, but Q4 still carries the biggest spend share.", size=16, weight=600, fill="#0f766e"))
    parts.append(svg_text(706, 486, "Signal", size=18, weight=700, fill="#925f10", anchor="middle"))
    parts.append(svg_text(706, 520, "Category +", size=20, weight=700, fill="#0f172a", anchor="middle"))
    parts.append(svg_text(706, 548, "income mix", size=20, weight=700, fill="#0f172a", anchor="middle"))

    parts.append(svg_text(878, 760, "Public-data consumer analytics for portfolio storytelling, segmentation, and strategic interpretation.", size=16, fill="#64748b"))

    parts.append("</svg>")
    path.write_text("\n".join(parts), encoding="utf-8")


def build_preview_page(path: Path, summary: dict[str, object]) -> None:
    title = summary["project_title"]
    subtitle = summary["project_summary"]
    html_doc = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(str(title))} Preview</title>
  <style>
    :root {{
      --bg: #f7f3eb;
      --paper: #fffdf9;
      --ink: #111827;
      --muted: #4b5563;
      --line: #e8dcc7;
      --accent: #0f766e;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Georgia, "Times New Roman", serif;
      background: radial-gradient(circle at top right, #fef3c7 0, transparent 28%), var(--bg);
      color: var(--ink);
    }}
    main {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 48px 24px 72px;
    }}
    .card {{
      background: var(--paper);
      border: 1px solid var(--line);
      border-radius: 28px;
      padding: 28px;
      margin-bottom: 28px;
      box-shadow: 0 16px 40px rgba(17, 24, 39, 0.05);
    }}
    h1, h2 {{
      margin: 0 0 14px;
    }}
    p {{
      line-height: 1.7;
      color: var(--muted);
    }}
    .eyebrow {{
      color: var(--accent);
      font-weight: 700;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      font-size: 0.8rem;
      margin-bottom: 12px;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 18px;
    }}
    .metric {{
      background: #fffbeb;
      border: 1px solid #f5e7c8;
      border-radius: 20px;
      padding: 18px;
    }}
    .metric strong {{
      display: block;
      font-size: 1.35rem;
      margin-top: 8px;
      color: var(--ink);
    }}
    img {{
      width: 100%;
      border-radius: 20px;
      border: 1px solid var(--line);
      background: #fff;
    }}
    ul {{
      margin: 0;
      padding-left: 20px;
      color: var(--muted);
      line-height: 1.7;
    }}
    a {{
      color: #0b61a4;
    }}
  </style>
</head>
<body>
  <main>
    <section class="card">
      <div class="eyebrow">Draft Portfolio Project</div>
      <h1>{html.escape(str(title))}</h1>
      <p>{html.escape(str(subtitle))}</p>
      <div class="grid">
        <div class="metric"><span>Latest retail month</span><strong>{html.escape(str(summary['retail_latest_month_label']))}</strong></div>
        <div class="metric"><span>Latest sentiment reading</span><strong>{html.escape(str(summary['sentiment_latest_value']))} in {html.escape(str(summary['sentiment_latest_month_label']))}</strong></div>
        <div class="metric"><span>Latest OI month</span><strong>{html.escape(str(summary['oi_latest_month_label']))}</strong></div>
      </div>
    </section>
    <section class="card">
      <div class="eyebrow">Visual Assets</div>
      <div class="grid">
        <img src="consumer-demand-signal-cover.svg" alt="Project cover">
        <img src="retail-real-index.svg" alt="Retail real index chart">
        <img src="income-heatmap-latest.svg" alt="Income heatmap chart">
        <img src="income-share-slope.svg" alt="Income share slope chart">
      </div>
    </section>
    <section class="card">
      <div class="eyebrow">What The Story Says</div>
      <ul>
        {''.join(f'<li>{html.escape(point)}</li>' for point in summary['key_takeaways'])}
      </ul>
    </section>
  </main>
</body>
</html>
"""
    path.write_text(html_doc, encoding="utf-8")


def build_summary() -> dict[str, object]:
    ensure_dirs()

    fetch_to_path(OI_MONTHLY_URL, RAW_DIR / "affinity_national_monthly.csv")
    fetch_to_path(OI_SHARES_2020_URL, RAW_DIR / "affinity_income_shares_national_2020.csv")
    fetch_to_path(OI_DOC_URL, RAW_DIR / "oi_tracker_data_documentation.md")
    fetch_to_path(OI_DICT_URL, RAW_DIR / "oi_tracker_data_dictionary.md")

    for series_id in FRED_SERIES.values():
        fetch_to_path(
            f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}",
            RAW_DIR / f"{series_id}.csv",
        )

    fred_data = {
        name: load_fred_series(RAW_DIR / f"{series_id}.csv", series_id)
        for name, series_id in FRED_SERIES.items()
    }
    retail_full_dates = sorted(set.intersection(*(set(fred_data[name].keys()) for name in FRED_LABELS), set(fred_data["sentiment"].keys())))
    cpi_filled = interpolated_month_map(fred_data["cpi"], retail_full_dates)
    common_retail_dates = [current for current in retail_full_dates if current >= date(2019, 1, 1) and current in cpi_filled]

    retail_real_index: dict[str, dict[date, float]] = {}
    retail_yoy: dict[str, dict[date, float]] = {}
    retail_share_shift: dict[str, float] = {}
    retail_low_sentiment_growth: dict[str, float] = {}
    retail_sentiment_corr: dict[str, float] = {}
    processed_rows: list[dict[str, str]] = []

    for name in FRED_LABELS:
        deflated = {
            current: (fred_data[name][current] / cpi_filled[current]) * 100
            for current in common_retail_dates
        }
        base_2019 = mean(value for current, value in deflated.items() if current.year == 2019)
        retail_real_index[name] = {
            current: (value / base_2019) * 100 for current, value in deflated.items()
        }
        retail_yoy[name] = {}
        yoy_values: list[float] = []
        sentiment_values: list[float] = []
        low_sentiment_values: list[float] = []
        for current in common_retail_dates:
            previous = previous_month_same_year(common_retail_dates, current)
            yoy = ""
            if previous:
                yoy_float = ((retail_real_index[name][current] / retail_real_index[name][previous]) - 1) * 100
                retail_yoy[name][current] = yoy_float
                yoy = f"{yoy_float:.2f}"
                yoy_values.append(yoy_float)
                sentiment_values.append(fred_data["sentiment"][current])
                if fred_data["sentiment"][current] < 70:
                    low_sentiment_values.append(yoy_float)
            processed_rows.append(
                {
                    "date": format_iso(current),
                    "category": FRED_LABELS[name],
                    "category_key": name,
                    "real_index_2019_avg_100": f"{retail_real_index[name][current]:.2f}",
                    "real_yoy_pct": yoy,
                    "sentiment": f"{fred_data['sentiment'][current]:.1f}",
                }
            )
        share_2019 = mean(
            fred_data[name][current] / sum(fred_data[peer][current] for peer in FRED_LABELS)
            for current in common_retail_dates
            if current.year == 2019
        )
        latest_retail_month = common_retail_dates[-1]
        latest_share = fred_data[name][latest_retail_month] / sum(fred_data[peer][latest_retail_month] for peer in FRED_LABELS)
        retail_share_shift[name] = (latest_share - share_2019) * 100
        retail_low_sentiment_growth[name] = mean(low_sentiment_values) if low_sentiment_values else 0.0
        retail_sentiment_corr[name] = pearson(sentiment_values, yoy_values) or 0.0

    write_csv(
        PROCESSED_DIR / "fred_real_retail_index.csv",
        ["date", "category", "category_key", "real_index_2019_avg_100", "real_yoy_pct", "sentiment"],
        processed_rows,
    )

    oi_records = load_oi_monthly(RAW_DIR / "affinity_national_monthly.csv")
    latest_oi_month, latest_oi_row = oi_records[-1]
    oi_latest_matrix: list[tuple[str, dict[str, float]]] = []
    oi_processed_rows: list[dict[str, str]] = []
    oi_gap_since_2024: dict[str, float] = {}
    for category_key, (label, series_prefix) in OI_CATEGORIES.items():
        values_for_latest: dict[str, float] = {}
        gap_samples: list[float] = []
        for quartile in QUARTILE_LABELS:
            latest_value = float(latest_oi_row[f"{series_prefix}_{quartile}"]) * 100
            values_for_latest[quartile] = latest_value
        oi_latest_matrix.append((label, values_for_latest))
        for current_month, row in oi_records:
            formatted = {
                "date": format_iso(current_month),
                "category": label,
                "category_key": category_key,
            }
            for quartile in QUARTILE_LABELS:
                current_value = float(row[f"{series_prefix}_{quartile}"]) * 100
                formatted[quartile] = f"{current_value:.2f}"
            oi_processed_rows.append(formatted)
            if current_month >= date(2024, 1, 1):
                gap_samples.append((float(row[f"{series_prefix}_q1"]) - float(row[f"{series_prefix}_q4"])) * 100)
        oi_gap_since_2024[category_key] = mean(gap_samples)

    write_csv(
        PROCESSED_DIR / "oi_income_category_growth.csv",
        ["date", "category", "category_key", *QUARTILE_LABELS.keys()],
        oi_processed_rows,
    )

    baseline_shares = load_income_shares(RAW_DIR / "affinity_income_shares_national_2020.csv")
    latest_all_values = {
        quartile: float(latest_oi_row[f"{OI_CATEGORIES['all'][1]}_{quartile}"]) for quartile in QUARTILE_LABELS
    }
    weighted_totals = {
        quartile: baseline_shares[quartile] * (1 + latest_all_values[quartile])
        for quartile in QUARTILE_LABELS
    }
    weighted_total_sum = sum(weighted_totals.values())
    estimated_latest_shares = {
        quartile: weighted_totals[quartile] / weighted_total_sum for quartile in QUARTILE_LABELS
    }
    share_rows = [
        {
            "quartile": quartile,
            "baseline_share_pct": f"{baseline_shares[quartile] * 100:.2f}",
            "estimated_latest_share_pct": f"{estimated_latest_shares[quartile] * 100:.2f}",
        }
        for quartile in QUARTILE_LABELS
    ]
    write_csv(
        PROCESSED_DIR / "estimated_income_share_shift.csv",
        ["quartile", "baseline_share_pct", "estimated_latest_share_pct"],
        share_rows,
    )

    retail_latest_summary = {
        key: round(retail_real_index[key][common_retail_dates[-1]], 1)
        for key in FRED_LABELS
    }
    retail_latest_yoy = {
        key: round(retail_yoy[key][common_retail_dates[-1]], 1)
        for key in FRED_LABELS
    }
    retail_share_shift_summary = {key: round(value, 2) for key, value in retail_share_shift.items()}
    most_resilient_category = max(retail_latest_summary, key=retail_latest_summary.get)
    most_pressured_category = min(retail_latest_summary, key=retail_latest_summary.get)
    biggest_income_gap_category = max(oi_gap_since_2024, key=oi_gap_since_2024.get)

    sentiment_latest_month = max(fred_data["sentiment"])
    sentiment_latest_value = fred_data["sentiment"][sentiment_latest_month]
    sentiment_since_2000 = [value for current, value in fred_data["sentiment"].items() if current >= date(2000, 1, 1)]
    weaker_than_latest = sum(value <= sentiment_latest_value for value in sentiment_since_2000)
    sentiment_percentile = round((weaker_than_latest / len(sentiment_since_2000)) * 100, 1)

    key_takeaways = [
        (
            f"E-commerce was {retail_latest_summary['ecommerce'] - 100:+.1f}% above its 2019 real-sales baseline in "
            f"{format_month(common_retail_dates[-1])}, the strongest structural gain in the retail basket."
        ),
        (
            f"Restaurants were still {retail_latest_summary['restaurants'] - 100:+.1f}% above 2019 in real terms even "
            f"though Michigan sentiment was only {sentiment_latest_value:.1f} in {format_month(sentiment_latest_month)}."
        ),
        (
            f"Furniture remained {retail_latest_summary['furniture'] - 100:+.1f}% below its 2019 real-sales baseline, "
            "signaling the weakest demand among the tracked discretionary categories."
        ),
        (
            f"In Opportunity Insights' {format_month(latest_oi_month)} cut, all-spending growth was {oi_latest_matrix[0][1]['q1']:.1f}% "
            f"for Q1 low-income ZIP codes versus {oi_latest_matrix[0][1]['q4']:.1f}% for Q4 high-income ZIP codes."
        ),
        (
            f"High-income ZIP codes still anchored the largest share of baseline card spend at {baseline_shares['q4'] * 100:.1f}%, "
            f"and an estimated {estimated_latest_shares['q4'] * 100:.1f}% in the latest month."
        ),
    ]

    summary: dict[str, object] = {
        "project_title": "Consumer Demand Signal: Where Spending Is Holding Up in 2026",
        "project_slug": "consumer-demand-signal-2026",
        "project_summary": (
            "A consumer analytics case study that combines retail sales, consumer sentiment, and income-segment card-spend data "
            "to show where demand is resilient and where discretionary pressure is still visible."
        ),
        "article_title": "Consumer Spending Is Not One Story",
        "article_slug": "consumer-spending-is-not-one-story",
        "retail_latest_month": format_iso(common_retail_dates[-1]),
        "retail_latest_month_label": format_month(common_retail_dates[-1]),
        "oi_latest_month": format_iso(latest_oi_month),
        "oi_latest_month_label": format_month(latest_oi_month),
        "sentiment_latest_month": format_iso(sentiment_latest_month),
        "sentiment_latest_month_label": format_month(sentiment_latest_month),
        "sentiment_latest_value": round(sentiment_latest_value, 1),
        "sentiment_percentile_since_2000": sentiment_percentile,
        "retail_latest_summary": retail_latest_summary,
        "retail_latest_yoy": retail_latest_yoy,
        "retail_share_shift_pp": retail_share_shift_summary,
        "retail_sentiment_corr": {key: round(value, 3) for key, value in retail_sentiment_corr.items()},
        "oi_latest_pct_change": {
            category_key: {quartile: round(value, 1) for quartile, value in values.items()}
            for category_key, (_, values) in zip(OI_CATEGORIES.keys(), oi_latest_matrix)
        },
        "baseline_income_share_pct": {quartile: round(value * 100, 1) for quartile, value in baseline_shares.items()},
        "estimated_latest_income_share_pct": {quartile: round(value * 100, 1) for quartile, value in estimated_latest_shares.items()},
        "biggest_income_gap_category": biggest_income_gap_category,
        "most_resilient_category": most_resilient_category,
        "most_pressured_category": most_pressured_category,
        "key_takeaways": key_takeaways,
        "source_links": {
            "opportunity_insights_monthly": OI_MONTHLY_URL,
            "opportunity_insights_shares_2020": OI_SHARES_2020_URL,
            "opportunity_insights_documentation": OI_DOC_URL,
            "opportunity_insights_dictionary": OI_DICT_URL,
            **FRED_SOURCE_LINKS,
        },
    }

    (PROCESSED_DIR / "consumer_demand_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    chart_dates = common_retail_dates
    chart_series = OrderedDict((name, [retail_real_index[name][current] for current in chart_dates]) for name in RETAIL_COLORS)
    build_line_chart(
        ARTIFACT_DIR / "retail-real-index.svg",
        chart_dates,
        chart_series,
        "Real Retail Demand by Category",
        f"CPI-adjusted monthly retail sales indexed to the 2019 average. Latest common month: {format_month(common_retail_dates[-1])}.",
    )
    build_heatmap(
        ARTIFACT_DIR / "income-heatmap-latest.svg",
        oi_latest_matrix,
        "Income-Segment Spend Snapshot",
        f"Opportunity Insights national monthly consumer spending by category. Latest month: {format_month(latest_oi_month)}.",
    )
    build_slope_chart(
        ARTIFACT_DIR / "income-share-slope.svg",
        baseline_shares,
        estimated_latest_shares,
        "Relative Growth Changed Less Than Spend Concentration",
        "Q1 ZIP codes are growing faster versus baseline, but Q4 still carries the largest share of total spending.",
    )
    build_cover(
        ARTIFACT_DIR / "consumer-demand-signal-cover.svg",
        "Consumer Demand Signal",
        "Where spending is holding up by category and income segment",
        [
            f"E-commerce: {retail_latest_summary['ecommerce'] - 100:+.1f}% vs 2019",
            f"Restaurants: {retail_latest_summary['restaurants'] - 100:+.1f}% vs 2019",
            f"Q1 all spend: {oi_latest_matrix[0][1]['q1']:.0f}% vs Jan 2020",
            f"Q4 share: {estimated_latest_shares['q4'] * 100:.1f}% est.",
        ],
    )
    build_preview_page(ARTIFACT_DIR / "portfolio-preview.html", summary)
    return summary


def project_markdown(summary: dict[str, object]) -> str:
    retail = summary["retail_latest_summary"]
    retail_share = summary["retail_share_shift_pp"]
    income = summary["oi_latest_pct_change"]
    baseline_share = summary["baseline_income_share_pct"]
    estimated_share = summary["estimated_latest_income_share_pct"]

    return f"""## Context
Weak consumer confidence does not automatically translate into weak demand. The real challenge for consumer teams is knowing **which categories are still structurally resilient** and **which pockets of demand look strong only because the benchmark is misleading**.

## Question
Where is U.S. consumer demand still holding up in 2026, and how does the answer change when I look at both category-level sales and income-segment spending behavior?

## Data Sources
- [Opportunity Insights Economic Tracker monthly consumer spending data]({summary['source_links']['opportunity_insights_monthly']})
- [Opportunity Insights data documentation]({summary['source_links']['opportunity_insights_documentation']})
- [Opportunity Insights Jan 2020 income shares]({summary['source_links']['opportunity_insights_shares_2020']})
- [FRED: University of Michigan Consumer Sentiment]({summary['source_links']['sentiment']})
- [FRED: Consumer Price Index]({summary['source_links']['cpi']})
- [FRED: E-commerce retail sales]({summary['source_links']['ecommerce']})
- [FRED: Food services and drinking places]({summary['source_links']['restaurants']})
- [FRED: Clothing stores]({summary['source_links']['clothing']})
- [FRED: Furniture stores]({summary['source_links']['furniture']})
- [FRED: Grocery stores]({summary['source_links']['grocery']})
- [FRED: General merchandise stores]({summary['source_links']['general_merchandise']})

## What I Built
- A refreshed data pull that combines public consumer card-spend, retail-sales, inflation, and sentiment series
- A real-sales index for six retail categories, normalized to a 2019 baseline
- An income-segment view of spending change by category using Opportunity Insights' monthly Affinity cut
- A simple share model to separate **relative growth** from **absolute dollar concentration**

## Key Findings
- **E-commerce remained the strongest structural winner.** In {summary['retail_latest_month_label']}, real e-commerce sales were {retail['ecommerce'] - 100:+.1f}% versus the 2019 average and gained {retail_share['ecommerce']:+.2f} percentage points of share inside the tracked retail basket.
- **Experiences stayed healthier than big-ticket goods.** Restaurants were still {retail['restaurants'] - 100:+.1f}% above the 2019 baseline, while furniture was {retail['furniture'] - 100:+.1f}% below it.
- **Low-income ZIP codes showed stronger relative growth than high-income ZIP codes.** In Opportunity Insights' {summary['oi_latest_month_label']} monthly release, total spending was up {income['all']['q1']:.1f}% for Q1 ZIP codes versus {income['all']['q4']:.1f}% for Q4 ZIP codes relative to the January 2020 baseline.
- **High-income households still mattered most in dollar terms.** Q4 ZIP codes represented {baseline_share['q4']:.1f}% of baseline card spend and an estimated {estimated_share['q4']:.1f}% in the latest month even after the slower relative growth.
- **General merchandise had the widest persistent income gap.** Since 2024, low-income ZIP codes have consistently outpaced high-income ZIP codes the most in general merchandise, which is a useful signal for value positioning and mass-channel planning.

## Why It Matters
This is the kind of work I want to keep doing: connecting external demand signals to concrete business questions around category risk, customer mix, channel strategy, and message prioritization. The project is especially relevant to consumer analytics, customer insights, business intelligence, and commercial strategy roles because it shows how I move from public data to decisions, not just charts.

## Output Assets
- `analysis/consumer-demand-signal/artifacts/retail-real-index.svg`
- `analysis/consumer-demand-signal/artifacts/income-heatmap-latest.svg`
- `analysis/consumer-demand-signal/artifacts/income-share-slope.svg`
- `analysis/consumer-demand-signal/data/processed/consumer_demand_summary.json`
"""


def article_markdown(summary: dict[str, object]) -> str:
    retail = summary["retail_latest_summary"]
    retail_share = summary["retail_share_shift_pp"]
    income = summary["oi_latest_pct_change"]
    baseline_share = summary["baseline_income_share_pct"]
    estimated_share = summary["estimated_latest_income_share_pct"]

    return f"""## The headline consumer story is too simple
If you only look at confidence headlines, the U.S. consumer looks fragile. The University of Michigan's consumer sentiment reading was just {summary['sentiment_latest_value']:.1f} in {summary['sentiment_latest_month_label']}, which puts it near the bottom of its post-2000 range.

But weak confidence has not translated into a uniform pullback.

That is what stood out when I combined public retail-sales data from FRED with Opportunity Insights' monthly consumer spending cuts. The more useful question is not whether the consumer is weak or strong. It is **where demand is still structurally holding up, where it is clearly softer, and how the answer changes once income mix enters the picture**.

## Convenience still looks like a structural win
The cleanest signal in the retail data is e-commerce.

After adjusting retail sales for inflation and indexing each category to its 2019 average, e-commerce sat {retail['ecommerce'] - 100:+.1f}% above baseline in {summary['retail_latest_month_label']}. It also picked up {retail_share['ecommerce']:+.2f} percentage points of share in the basket I tracked, by far the biggest positive shift among the categories in this analysis.

That matters because it looks less like a temporary bounce and more like a durable behavior change. If I were supporting a brand, retailer, or marketplace team, I would treat convenience-led demand as something to plan around rather than something to wait out.

## Experience categories held up better than big-ticket demand
The second pattern is a split between experience spending and heavier discretionary goods.

Restaurants remained {retail['restaurants'] - 100:+.1f}% above their 2019 real-sales baseline even with confidence still soft. Furniture, by contrast, was {retail['furniture'] - 100:+.1f}% below baseline, and clothing was {retail['clothing'] - 100:+.1f}% below baseline.

This is the kind of pattern that matters for budgeting and prioritization. If a commercial team treats all discretionary demand the same way, it will miss the fact that consumers can still make room for convenience and experience while delaying larger or more deferrable purchases.

## Income segmentation changes the interpretation
The Opportunity Insights data adds a second layer that is easy to miss if I only look at top-line category numbers.

In the {summary['oi_latest_month_label']} national monthly release:

- all spending was up {income['all']['q1']:.1f}% for Q1 low-income ZIP codes versus {income['all']['q4']:.1f}% for Q4 high-income ZIP codes relative to January 2020
- grocery was up {income['grocery']['q1']:.1f}% for Q1 and {income['grocery']['q4']:.1f}% for Q4
- restaurants and hotels were up {income['restaurants_hotels']['q1']:.1f}% for Q1 and {income['restaurants_hotels']['q4']:.1f}% for Q4
- general merchandise was up {income['general_merchandise']['q1']:.1f}% for Q1 and {income['general_merchandise']['q4']:.1f}% for Q4

The first takeaway is that lower-income ZIP codes are showing faster **relative growth** versus their own baseline in several categories.

The second takeaway is the one that keeps the story honest: faster relative growth does not mean lower-income households have become the biggest source of category dollars. Opportunity Insights' own baseline share file shows that Q4 ZIP codes accounted for {baseline_share['q4']:.1f}% of card spend in January 2020 versus just {baseline_share['q1']:.1f}% for Q1. Re-weighting those baseline shares by the latest all-spending index still leaves Q4 at an estimated {estimated_share['q4']:.1f}% of total spend, compared with {estimated_share['q1']:.1f}% for Q1.

That distinction matters a lot in business settings. Growth rate alone can overstate the size of an opportunity. Dollar concentration alone can hide where momentum is improving.

## What I would do with this if I were supporting a consumer business
This kind of analysis leads to a few practical decisions:

- Protect channels and journeys built around convenience because that demand looks durable.
- Treat restaurants and experience-adjacent demand differently from big-ticket discretionary demand.
- Segment growth conversations carefully: a category can show better momentum in lower-income ZIP codes while still depending heavily on higher-income households for absolute scale.
- Prioritize reporting that separates **relative recovery**, **share shift**, and **dollar concentration** instead of blending them into one headline KPI.

## Why this project is useful for my portfolio
I built this project to reflect the type of analytics work I want to do more of: framing a business question clearly, pulling trustworthy public data, reconciling multiple signals, and translating them into a view a cross-functional team could actually act on.

That combination is what makes consumer analytics interesting to me. The goal is not only to describe what happened. It is to decide what matters, what is noise, and what the business should do next.

## Research Notes
- [Opportunity Insights Economic Tracker monthly Affinity data]({summary['source_links']['opportunity_insights_monthly']})
- [Opportunity Insights methodology and processing notes]({summary['source_links']['opportunity_insights_documentation']})
- [Opportunity Insights variable dictionary]({summary['source_links']['opportunity_insights_dictionary']})
- [FRED consumer sentiment series]({summary['source_links']['sentiment']})
- [FRED CPI series]({summary['source_links']['cpi']})
- [FRED retail category series]({summary['source_links']['ecommerce']}), [restaurants]({summary['source_links']['restaurants']}), [clothing]({summary['source_links']['clothing']}), [furniture]({summary['source_links']['furniture']}), [grocery]({summary['source_links']['grocery']}), and [general merchandise]({summary['source_links']['general_merchandise']})
"""


def metadata_json(summary: dict[str, object]) -> str:
    metadata = {
        "project": {
            "title": summary["project_title"],
            "slug": summary["project_slug"],
            "summary": summary["project_summary"],
            "published_on": "2026-04-28",
            "read_time": "6 min read",
            "tags": [
                "consumer analytics",
                "customer insights",
                "retail analytics",
                "segmentation",
                "public data",
            ],
            "accent": "sunrise",
            "suggested_cover_asset": "consumer-demand-signal-cover.svg",
            "published": False,
            "featured": False,
        },
        "article": {
            "title": summary["article_title"],
            "slug": summary["article_slug"],
            "summary": (
                "Consumer confidence still looks weak, but category-level demand and income-segment data tell a more useful story "
                "about convenience, experience spending, and discretionary pressure."
            ),
            "published_on": "2026-04-28",
            "read_time": "7 min read",
            "tags": [
                "consumer insights",
                "spending trends",
                "income segmentation",
                "retail strategy",
                "analytics",
            ],
            "accent": "sunrise",
            "suggested_cover_asset": "consumer-demand-signal-cover.svg",
            "published": False,
            "featured": False,
        },
    }
    return json.dumps(metadata, indent=2)


def main() -> None:
    summary = build_summary()
    (DRAFT_DIR / "website_project.md").write_text(project_markdown(summary), encoding="utf-8")
    (DRAFT_DIR / "website_article.md").write_text(article_markdown(summary), encoding="utf-8")
    (DRAFT_DIR / "website_metadata.json").write_text(metadata_json(summary), encoding="utf-8")


if __name__ == "__main__":
    main()
