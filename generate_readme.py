#!/usr/bin/env python3
import re
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
CHARTS_DIR = ROOT / "charts"
README_PATH = ROOT / "README.md"
CHARTS_START = "<!-- CHARTS:START -->"
CHARTS_END = "<!-- CHARTS:END -->"

README_TEMPLATE = """# DBS Pop-up ATM Tracker

Tracks crowd data for DBS pop-up ATM locations in Singapore during the 2026 Lunar New Year notes exchange period.

## Data available

- `data/*.csv`: timestamped crowd snapshots in `YYYYMMDD-HHMMSS.csv` format.
- CSV columns: `id`, `postal`, `crowd`.
- `charts/*.svg`: one generated chart per day, based on the snapshots in `data/`.
- `atms.json`: metadata for ATM names, postal codes, and regions.

## Automation

- GitHub Actions workflow: `.github/workflows/scheduled-update.yml`.
- Schedule: every 5 minutes (plus manual runs with `workflow_dispatch`).
- Schedule and collection window are evaluated in Singapore time (`Asia/Singapore`).
- Each run saves a new snapshot only when the source CSV changes, then refreshes charts and this README.

## Daily charts

<!-- CHARTS:START -->
<!-- CHARTS:END -->

## Credits

Data and source pages by DBS:
- [DBS Lunar New Year notes 2026](https://www.dbs.com.sg/personal/lny-notes-2026)
- [DBS pop-up ATM page](https://www.dbs.com/pop-up-atm/index.html)
"""

def format_day(day_str: str) -> str:
    return datetime.strptime(day_str, "%Y%m%d").strftime("%Y-%m-%d")


def list_chart_days() -> list[str]:
    days = []
    for path in CHARTS_DIR.glob("*.svg"):
        if re.fullmatch(r"\d{8}", path.stem):
            days.append(path.stem)
    return sorted(days, reverse=True)


def count_snapshots_by_day() -> dict[str, int]:
    counts: dict[str, int] = {}
    for path in DATA_DIR.glob("*.csv"):
        match = re.fullmatch(r"(\d{8})-\d{6}\.csv", path.name)
        if not match:
            continue
        day = match.group(1)
        counts[day] = counts.get(day, 0) + 1
    return counts


def render_chart_section(day: str, counts: dict[str, int], latest: bool = False) -> list[str]:
    day_label = format_day(day)
    suffix = " (latest)" if latest else ""
    snapshots = counts.get(day, 0)
    return [
        f"### {day_label}{suffix}",
        f"- Snapshots: {snapshots}",
        f"![DBS pop-up ATM crowd chart for {day_label}](charts/{day}.svg)",
        "",
    ]


def build_charts_content(days: list[str], counts: dict[str, int]) -> str:
    lines: list[str] = []
    if not days:
        lines.append("No charts generated yet.")
    else:
        lines.extend(render_chart_section(days[0], counts, latest=True))
        if len(days) > 1:
            lines.extend(
                [
                    "<details>",
                    "<summary>Older days</summary>",
                    "",
                ]
            )
            for day in days[1:]:
                lines.extend(render_chart_section(day, counts))
            lines.extend(
                [
                    "</details>",
                    "",
                ]
            )
    return "\n".join(lines)


def ensure_readme_template() -> str:
    if not README_PATH.exists():
        README_PATH.write_text(README_TEMPLATE + "\n", encoding="utf-8")
    return README_PATH.read_text(encoding="utf-8")


def replace_charts_block(readme_text: str, charts_content: str) -> str:
    pattern = re.compile(
        rf"{re.escape(CHARTS_START)}\n[\s\S]*?{re.escape(CHARTS_END)}"
    )
    replacement = f"{CHARTS_START}\n{charts_content}\n{CHARTS_END}"
    if pattern.search(readme_text):
        return pattern.sub(replacement, readme_text, count=1)
    return readme_text.rstrip() + "\n\n## Daily charts\n\n" + replacement + "\n"


def main() -> None:
    days = list_chart_days()
    counts = count_snapshots_by_day()
    readme_text = ensure_readme_template()
    charts_content = build_charts_content(days, counts)
    updated = replace_charts_block(readme_text, charts_content)

    if updated == readme_text:
        print(f"No README changes ({README_PATH})")
        return

    README_PATH.write_text(updated, encoding="utf-8")
    print(f"Updated charts block in {README_PATH}")


if __name__ == "__main__":
    main()
