#!/usr/bin/env python3
import argparse
import csv
import glob
import json
import os
from datetime import datetime, time

DATA_DIR = 'data'
OUT_DIR = 'charts'

WIDTH = 780
PADDING_L = 210
PADDING_R = 20
ROW_H = 24
ROW_GAP = 10
TITLE_H = 48
AXIS_H = 24
LINE_COLOR = '#111111'
AREA_COLOR = '#d9e2e7'
AXIS_COLOR = '#666666'
GRID_COLOR = '#dfe6eb'
GRID_COLOR_STRONG = '#9aa8b3'
TEXT_COLOR = '#111111'
FONT = 'system-ui, -apple-system, Segoe UI, sans-serif'
FILL_YELLOW = '#f6e58d'
FILL_ORANGE = '#f3b562'
FILL_RED = '#e85f5c'

TITLE_Y = 18
TOP_AXIS_Y = 38
TOP_LABEL_Y = 32

STRONG_HOURS = {12, 15, 18, 21}


def esc(s: str) -> str:
    return (s.replace('&', '&amp;')
             .replace('<', '&lt;')
             .replace('>', '&gt;'))


def add_axis(svg_lines, axis_y, ticks, day_dt, x_for, label_y):
    svg_lines.append(
        f'  <line x1="{PADDING_L}" y1="{axis_y}" '
        f'x2="{WIDTH - PADDING_R}" y2="{axis_y}" '
        f'stroke="{AXIS_COLOR}" stroke-width="1"/>'
    )
    for hr in ticks:
        tick_ts = datetime.combine(day_dt.date(), time(hr, 0))
        x = x_for(tick_ts)
        svg_lines.append(
            f'  <line x1="{x:.2f}" y1="{axis_y}" '
            f'x2="{x:.2f}" y2="{axis_y + 4}" '
            f'stroke="{AXIS_COLOR}" stroke-width="1"/>'
        )
        if hr == 0:
            label = '12am'
        elif hr < 12:
            label = f'{hr}am'
        elif hr == 12:
            label = '12pm'
        else:
            label = f'{hr - 12}pm'
        svg_lines.append(f'  <text x="{x - 12:.2f}" y="{label_y}">{label}</text>')


def main():
    parser = argparse.ArgumentParser(description='Generate daily SVG charts.')
    parser.add_argument('date', nargs='?', help='Filter to a specific date (YYYYMMDD).')
    parser.add_argument('--date', dest='date_flag', help='Filter to a specific date (YYYYMMDD).')
    args = parser.parse_args()
    date_filter = args.date_flag or args.date

    os.makedirs(OUT_DIR, exist_ok=True)

    # postal -> name
    with open('atms.json', 'r', encoding='utf-8') as f:
        atm_data = json.load(f)
    name_by_postal = {}
    atm_by_postal = {}
    region_by_postal = {}
    for v in atm_data.values():
        postal = v.get('postal')
        name = v.get('name')
        atm = v.get('atm')
        total = v.get('total')
        region = v.get('region')
        if postal and name:
            name_by_postal[postal] = name
        if postal and region:
            region_by_postal[postal] = region
        atm_str = None
        if atm is not None:
            s = str(atm).strip()
            if s.isdigit():
                atm_str = s
        if atm_str is None and total is not None:
            s = str(total).strip()
            if s.isdigit():
                atm_str = s
        if postal and atm_str is not None:
            atm_by_postal[postal] = atm_str

    by_day = {}
    for path in glob.glob(os.path.join(DATA_DIR, '*.csv')):
        base = os.path.basename(path)
        if '-' not in base:
            continue
        date_part, rest = base.split('-', 1)
        time_part = rest.split('.', 1)[0]
        try:
            ts = datetime.strptime(date_part + time_part, '%Y%m%d%H%M%S')
        except ValueError:
            continue
        by_day.setdefault(date_part, []).append((ts, path))

    written = 0
    for day, items in by_day.items():
        if date_filter and day != date_filter:
            continue
        items.sort(key=lambda x: x[0])

        # Collect series per postal
        series = {}
        for ts, path in items:
            with open(path, newline='') as f:
                reader = csv.reader(f)
                _header = next(reader, None)
                for row in reader:
                    if len(row) < 3:
                        continue
                    postal = row[1]
                    try:
                        val = float(row[2])
                    except ValueError:
                        continue
                    if val > 500:
                        continue
                    series.setdefault(postal, []).append((ts, val))

        postals = sorted(series.keys())
        regions = {}
        for postal in postals:
            region = region_by_postal.get(postal, 'Unknown')
            regions.setdefault(region, []).append(postal)
        region_names = sorted(regions.keys())
        ordered_postals = []
        for region in region_names:
            ordered_postals.extend(
                sorted(
                    regions[region],
                    key=lambda p: name_by_postal.get(p, '')
                )
            )
        row_count = len(ordered_postals)
        plot_h = row_count * ROW_H + max(0, row_count - 1) * ROW_GAP
        height = TITLE_H + plot_h + AXIS_H

        # Fixed time range 10:00-22:00
        day_dt = datetime.strptime(day, '%Y%m%d')
        start_ts = datetime.combine(day_dt.date(), time(10, 0))
        end_ts = datetime.combine(day_dt.date(), time(22, 0))
        span = (end_ts - start_ts).total_seconds()
        plot_w = WIDTH - PADDING_L - PADDING_R

        def x_for(ts):
            t = (ts - start_ts).total_seconds()
            t = max(0, min(span, t))
            return PADDING_L + (t / span) * plot_w

        svg_lines = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}" '
            f'viewBox="0 0 {WIDTH} {height}" role="img" '
            f'aria-label="{day} crowd by postal">',
            f'  <style>text{{font-family:{FONT};fill:{TEXT_COLOR};font-size:12px;}}</style>',
            f'  <text x="{PADDING_L}" y="{TITLE_Y}" font-size="14" font-weight="600">{day}</text>',
        ]

        ticks = list(range(10, 23))
        # Grid lines (hourly)
        grid_top = TITLE_H
        grid_bottom = TITLE_H + plot_h
        for hr in ticks:
            tick_ts = datetime.combine(day_dt.date(), time(hr, 0))
            x = x_for(tick_ts)
            color = GRID_COLOR_STRONG if hr in STRONG_HOURS else GRID_COLOR
            svg_lines.append(
                f'  <line x1="{x:.2f}" y1="{grid_top}" '
                f'x2="{x:.2f}" y2="{grid_bottom}" '
                f'stroke="{color}" stroke-width="1"/>'
            )

        # Top axis
        add_axis(svg_lines, TOP_AXIS_Y, ticks, day_dt, x_for, TOP_LABEL_Y)

        # Use a shared max scale across all rows in the day
        day_max = 0
        for _postal, pts in series.items():
            if not pts:
                continue
            local_max = max(v for _, v in pts)
            if local_max > day_max:
                day_max = local_max

        # Draw each postal area chart
        for i, postal in enumerate(ordered_postals):
            y_top = TITLE_H + i * (ROW_H + ROW_GAP)
            y_mid = y_top + ROW_H / 2
            y_base = y_top + ROW_H - 4
            values = sorted(series[postal], key=lambda x: x[0])
            if not values:
                continue
            vals = [v for _, v in values]
            max_v = day_max
            if max_v == 0:
                def y_for(_v):
                    return y_mid
            else:
                def y_for(v):
                    v = max(0, v)
                    return y_top + 4 + (max_v - v) / max_v * (ROW_H - 8)

            points = [(x_for(ts), y_for(v)) for ts, v in values]
            if not points:
                continue

            label_name = name_by_postal.get(postal, '')
            name_text = esc(label_name) if label_name else ''
            atm_count = atm_by_postal.get(postal, '')
            suffix = f' \U0001f3e7 {atm_count}' if atm_count else ''
            postal_text = esc(f'{postal}{suffix}')
            label_x = 60
            svg_lines.append(f'  <text x="{label_x}" y="{y_mid - 2:.2f}" font-weight="600">{name_text}</text>')
            svg_lines.append(f'  <text x="{label_x}" y="{y_mid + 12:.2f}" fill="{TEXT_COLOR}" opacity="0.5">{postal_text}</text>')

            # Area path
            path_parts = [f'M {points[0][0]:.2f},{points[0][1]:.2f}']
            for x, y in points[1:]:
                path_parts.append(f'L {x:.2f},{y:.2f}')
            path_parts.append(f'L {points[-1][0]:.2f},{y_base:.2f}')
            path_parts.append(f'L {points[0][0]:.2f},{y_base:.2f} Z')
            path_d = ' '.join(path_parts)

            clip_id = f'clip-{day}-{i}'
            svg_lines.append('  <defs>')
            svg_lines.append(f'    <clipPath id="{clip_id}">')
            svg_lines.append(f'      <path d="{path_d}"/>')
            svg_lines.append('    </clipPath>')
            svg_lines.append('  </defs>')

            # Threshold bands (0-14, 14-28, 28+)
            top = y_top + 4
            bottom = y_base
            y_14 = max(top, min(bottom, y_for(14)))
            y_28 = max(top, min(bottom, y_for(28)))

            # Arrange from top (high values) to bottom (low values)
            band_red_top = top
            band_red_bot = max(top, min(bottom, y_28))
            band_orange_top = band_red_bot
            band_orange_bot = max(band_orange_top, min(bottom, y_14))
            band_yellow_top = band_orange_bot
            band_yellow_bot = bottom

            svg_lines.append(f'  <rect x="{PADDING_L}" y="{band_red_top:.2f}" width="{plot_w:.2f}" height="{band_red_bot - band_red_top:.2f}" fill="{FILL_RED}" clip-path="url(#{clip_id})"/>')
            svg_lines.append(f'  <rect x="{PADDING_L}" y="{band_orange_top:.2f}" width="{plot_w:.2f}" height="{band_orange_bot - band_orange_top:.2f}" fill="{FILL_ORANGE}" clip-path="url(#{clip_id})"/>')
            svg_lines.append(f'  <rect x="{PADDING_L}" y="{band_yellow_top:.2f}" width="{plot_w:.2f}" height="{band_yellow_bot - band_yellow_top:.2f}" fill="{FILL_YELLOW}" clip-path="url(#{clip_id})"/>')
            svg_lines.append(
                f'  <polyline fill="none" stroke="{LINE_COLOR}" stroke-width="1.2" '
                f'points="' + ' '.join(f'{x:.2f},{y:.2f}' for x, y in points) + '"/>'
            )

        # Bottom axis
        axis_y = TITLE_H + plot_h + 8
        add_axis(svg_lines, axis_y, ticks, day_dt, x_for, axis_y + 16)

        # Region separators and labels
        region_start_index = 0
        for region in region_names:
            group = regions[region]
            if not group:
                continue
            start_idx = region_start_index
            end_idx = region_start_index + len(group) - 1
            if end_idx < row_count - 1:
                y_sep = TITLE_H + (end_idx + 1) * (ROW_H + ROW_GAP) - (ROW_GAP / 2)
                svg_lines.append(
                    f'  <line x1="{PADDING_L}" y1="{y_sep:.2f}" '
                    f'x2="{WIDTH - PADDING_R}" y2="{y_sep:.2f}" '
                    f'stroke="#222222" stroke-width="1.2"/>'
                )
            y_group_top = TITLE_H + start_idx * (ROW_H + ROW_GAP)
            y_group_bottom = TITLE_H + (end_idx + 1) * (ROW_H + ROW_GAP) - ROW_GAP
            y_center = (y_group_top + y_group_bottom) / 2
            svg_lines.append(
                f'  <text x="24" y="{y_center:.2f}" font-size="11" '
                f'font-weight="600" fill="{TEXT_COLOR}" '
                f'text-anchor="middle" transform="rotate(-90 24 {y_center:.2f})">{esc(region)}</text>'
            )
            region_start_index += len(group)

        svg_lines.append('</svg>')

        out_path = os.path.join(OUT_DIR, f'{day}.svg')
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(svg_lines) + '\n')
        written += 1

    print(f'Wrote {written} chart(s) to {OUT_DIR}/')


if __name__ == '__main__':
    main()
