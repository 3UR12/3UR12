#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import html
import json
import os
import pathlib
import urllib.request
from dataclasses import dataclass

USERNAME = os.getenv("GITHUB_USERNAME", "3UR12")
TOKEN = os.getenv("GITHUB_TOKEN", "")
OUT = pathlib.Path("assets")
OUT.mkdir(parents=True, exist_ok=True)

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays { contributionCount date weekday }
        }
      }
    }
  }
}
"""

THEMES = {
    "dark": {
        "bg": "#0d1117", "panel": "#161b22", "border": "#30363d",
        "text": "#f0f6fc", "muted": "#8b949e", "accent": "#2f81f7",
        "levels": ["#21262d", "#0e4429", "#006d32", "#26a641", "#39d353"],
    },
    "light": {
        "bg": "#ffffff", "panel": "#f6f8fa", "border": "#d0d7de",
        "text": "#1f2328", "muted": "#59636e", "accent": "#0969da",
        "levels": ["#ebedf0", "#9be9a8", "#40c463", "#30a14e", "#216e39"],
    },
}


@dataclass(frozen=True)
class Day:
    date: dt.date
    count: int
    weekday: int


def fetch_activity() -> tuple[list[Day], int]:
    headers = {"Content-Type": "application/json", "User-Agent": "3UR12-profile-readme"}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    request = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": USERNAME}}).encode(),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=25) as response:
        payload = json.loads(response.read().decode())
    if payload.get("errors"):
        raise RuntimeError(payload["errors"])
    calendar = payload["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    days = [
        Day(dt.date.fromisoformat(item["date"]), int(item["contributionCount"]), int(item["weekday"]))
        for week in calendar["weeks"]
        for item in week["contributionDays"]
    ]
    return sorted(days, key=lambda day: day.date), int(calendar["totalContributions"])


def level(count: int) -> int:
    if count <= 0: return 0
    if count == 1: return 1
    if count <= 3: return 2
    if count <= 6: return 3
    return 4


def streaks(days: list[Day]) -> tuple[int, int]:
    values = {day.date: day.count for day in days}
    cursor = dt.datetime.now(dt.timezone.utc).date()
    if values.get(cursor, 0) == 0:
        cursor -= dt.timedelta(days=1)
    current = 0
    while values.get(cursor, 0) > 0:
        current += 1
        cursor -= dt.timedelta(days=1)

    longest = running = 0
    previous = None
    for day in days:
        if day.count > 0:
            running = running + 1 if previous and day.date == previous + dt.timedelta(days=1) else 1
            longest = max(longest, running)
            previous = day.date
        else:
            running, previous = 0, None
    return current, longest


def weekly(days: list[Day]) -> list[int]:
    if not days: return []
    values = {day.date: day.count for day in days}
    first = days[0].date - dt.timedelta(days=(days[0].date.weekday() + 1) % 7)
    last = days[-1].date
    result = []
    cursor = first
    while cursor <= last:
        result.append(sum(values.get(cursor + dt.timedelta(days=i), 0) for i in range(7)))
        cursor += dt.timedelta(days=7)
    return result[-53:]


def error_svg(theme_name: str, message: str) -> str:
    t = THEMES[theme_name]
    safe = html.escape(message[:120])
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1100" height="310" viewBox="0 0 1100 310" role="img">
<rect width="100%" height="100%" rx="14" fill="{t['bg']}" stroke="{t['border']}"/>
<text x="42" y="45" fill="{t['text']}" font-size="20" font-weight="700" font-family="Segoe UI, Ubuntu, sans-serif">{USERNAME} / GitHub Activity</text>
<rect x="42" y="78" width="1016" height="170" rx="12" fill="{t['panel']}" stroke="{t['border']}"/>
<text x="550" y="150" text-anchor="middle" fill="{t['text']}" font-size="18" font-weight="600" font-family="Segoe UI, Ubuntu, sans-serif">Activity data is temporarily unavailable</text>
<text x="550" y="181" text-anchor="middle" fill="{t['muted']}" font-size="13" font-family="Segoe UI, Ubuntu, sans-serif">{safe}</text>
<text x="550" y="211" text-anchor="middle" fill="{t['muted']}" font-size="12" font-family="Segoe UI, Ubuntu, sans-serif">The scheduled workflow will retry automatically.</text>
<text x="42" y="285" fill="{t['muted']}" font-size="11" font-family="Segoe UI, Ubuntu, sans-serif">Self-hosted profile asset · no third-party stats endpoint</text>
</svg>'''


def render(theme_name: str, days: list[Day], total: int) -> str:
    t = THEMES[theme_name]
    active = sum(day.count > 0 for day in days)
    current, longest = streaks(days)
    weeks = weekly(days)
    by_date = {day.date: day.count for day in days}

    last = days[-1].date
    last_saturday = last + dt.timedelta(days=(5 - last.weekday()) % 7)
    first_sunday = last_saturday - dt.timedelta(days=370)

    cells = []
    for w in range(53):
        for d in range(7):
            date = first_sunday + dt.timedelta(days=w * 7 + d)
            count = by_date.get(date, 0)
            cells.append(
                f'<rect x="{42 + w*14}" y="{269 + d*14}" width="11" height="11" rx="2" fill="{t["levels"][level(count)]}"><title>{date}: {count} contribution(s)</title></rect>'
            )

    max_week = max(weeks or [1]) or 1
    denom = max(len(weeks) - 1, 1)
    points = " ".join(
        f"{42 + (i/denom)*1014:.1f},{239 - (value/max_week)*38:.1f}"
        for i, value in enumerate(weeks)
    )

    stats = [("Contributions", f"{total:,}"), ("Active days", str(active)), ("Current streak", f"{current}d"), ("Longest streak", f"{longest}d")]
    cards = []
    for x, (label_text, value) in zip((42, 309, 576, 843), stats):
        cards.append(f'<rect x="{x}" y="80" width="225" height="84" rx="10" fill="{t["panel"]}" stroke="{t["border"]}"/>')
        cards.append(f'<text x="{x+16}" y="108" fill="{t["muted"]}" font-size="13" font-family="Segoe UI, Ubuntu, sans-serif">{label_text}</text>')
        cards.append(f'<text x="{x+16}" y="144" fill="{t["text"]}" font-size="29" font-weight="700" font-family="Segoe UI, Ubuntu, sans-serif">{value}</text>')

    legend = []
    for i, color in enumerate(t["levels"]):
        legend.append(f'<rect x="{866+i*18}" y="374" width="11" height="11" rx="2" fill="{color}"/>')

    updated = dt.datetime.now(dt.timezone.utc).date().isoformat()
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1100" height="410" viewBox="0 0 1100 410" role="img" aria-labelledby="title desc">
<title id="title">{USERNAME} GitHub activity</title>
<desc id="desc">Automatically generated public contribution dashboard for {USERNAME}.</desc>
<rect width="100%" height="100%" rx="14" fill="{t['bg']}" stroke="{t['border']}"/>
<text x="42" y="40" fill="{t['text']}" font-size="20" font-weight="700" font-family="Segoe UI, Ubuntu, sans-serif">{USERNAME} / GitHub Activity</text>
<text x="42" y="62" fill="{t['muted']}" font-size="12" font-family="Segoe UI, Ubuntu, sans-serif">Public contribution activity · generated automatically from GitHub data</text>
{''.join(cards)}
<text x="42" y="193" fill="{t['text']}" font-size="13" font-weight="600" font-family="Segoe UI, Ubuntu, sans-serif">Weekly activity</text>
<line x1="42" y1="239" x2="1056" y2="239" stroke="{t['border']}"/>
<polyline points="{points}" fill="none" stroke="{t['accent']}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
<text x="42" y="261" fill="{t['text']}" font-size="13" font-weight="600" font-family="Segoe UI, Ubuntu, sans-serif">52-week contribution map</text>
{''.join(cells)}
<text x="42" y="384" fill="{t['muted']}" font-size="11" font-family="Segoe UI, Ubuntu, sans-serif">Updated {updated} · generated by GitHub Actions</text>
<text x="824" y="384" fill="{t['muted']}" font-size="11" font-family="Segoe UI, Ubuntu, sans-serif">Less</text>
{''.join(legend)}
<text x="960" y="384" fill="{t['muted']}" font-size="11" font-family="Segoe UI, Ubuntu, sans-serif">More</text>
</svg>'''


def main() -> None:
    try:
        days, total = fetch_activity()
        if not days:
            raise RuntimeError("GitHub returned an empty contribution calendar.")
        outputs = {theme: render(theme, days, total) for theme in THEMES}
    except Exception as exc:
        print(f"Activity generation warning: {exc}")
        outputs = {theme: error_svg(theme, str(exc)) for theme in THEMES}

    for theme, svg in outputs.items():
        path = OUT / f"profile-activity-{theme}.svg"
        path.write_text(svg, encoding="utf-8")
        print(f"Wrote {path}")


if __name__ == "__main__":
    main()
