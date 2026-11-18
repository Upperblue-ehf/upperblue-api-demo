"""Look up Reykjavík’s tide-table site and plot three days of predicted highs and lows."""

from datetime import UTC, date, datetime, timedelta

from matplotlib.figure import Figure
from matplotlib.ticker import MaxNLocator

from api import get
from cli import run


def fetch_tides(day):
    end = day + timedelta(days=3)
    catalogue = get("ocean/tides/sites/geojson", status="all", site_method="measured_reference")
    for feature in catalogue["features"]:
        site = feature["properties"]
        if (
            site["provider_id"] == "reykjavik"
            and site["site_approved"]
            and site["coverage_start"] <= day.isoformat()
            and (end - timedelta(days=1)).isoformat() <= site["coverage_end"]
        ):
            break
    else:
        raise ValueError(f"No Reykjavík tide-table edition covers all three days from {day}.")

    table = get(
        f"ocean/tides/sites/{site['tide_site_id']}/events",
        start_time=f"{day}T00:00:00Z",
        end_time=f"{end}T00:00:00Z",
        source_version=site["source_revision"],
    )
    if table["availability"] != "available" or not table["data"]:
        raise ValueError("No tide predictions available for this interval.")
    events = [
        {"time": row["valid_time"], "type": row["event_type"], "height": row["height_m"]}
        for row in table["data"]
    ]
    return {
        "day": day.isoformat(),
        "site": site["name_is"],
        "edition": site["source_revision"],
        "datum": site["vertical_reference"],
        "retrieved": datetime.now(UTC).date().isoformat(),
        "events": events,
    }


def draw(data, output):
    paper, ink, muted = "#f6f3eb", "#102d3b", "#476472"
    high, low = "#006759", "#aa4227"
    fig = Figure(figsize=(12, 6.5), facecolor=paper)
    fig.text(0.065, 0.90, "UPPERBLUE API   /   OCEAN", color=high, fontsize=10, family="monospace")
    fig.text(0.065, 0.77, f"{data['site']} tides", color=ink, fontsize=38, weight="bold")
    fig.text(
        0.065,
        0.70,
        f"{data['edition']}   ·   High and low water in metres above Icelandic chart datum",
        color=muted,
        fontsize=13,
    )
    ax = fig.add_axes((0.10, 0.23, 0.83, 0.37), facecolor=paper)
    start = datetime.combine(date.fromisoformat(data["day"]), datetime.min.time(), UTC)
    for event in data["events"]:
        if event["height"] is None:
            continue
        time = datetime.fromisoformat(event["time"])
        hours = (time - start).total_seconds() / 3600
        height = float(event["height"])
        is_high = event["type"] == "high"
        color = high if is_high else low
        ax.vlines(hours, min(0, height), max(0, height), color=color, alpha=0.45)
        ax.annotate(
            time.strftime("%H:%M"),
            (hours, 0),
            xytext=(0, -10),
            textcoords="offset points",
            ha="center",
            color=muted,
            fontsize=8,
        )
        ax.scatter(hours, height, marker="^" if is_high else "v", s=80, color=color, zorder=3)
        ax.annotate(
            f"{height:.1f}",
            (hours, height),
            xytext=(0, 9),
            textcoords="offset points",
            ha="center",
            color=ink,
            fontsize=10,
        )
    ticks = [0, 24, 48]
    ax.set_xticks(ticks, [(start + timedelta(hours=h)).strftime("%d %b") for h in ticks])
    ax.set_xlim(-2, 74)
    ax.margins(y=0.20)
    ax.yaxis.set_major_locator(MaxNLocator(nbins=4, integer=True))
    ax.set_axisbelow(True)
    ax.grid(axis="y", color=muted, alpha=0.18)
    ax.tick_params(colors=muted, length=0, pad=8)
    ax.tick_params(axis="x", pad=13)
    for spine in ax.spines.values():
        spine.set_visible(False)
    fig.text(0.065, 0.12, "▲  High tide", color=high, fontsize=12)
    fig.text(0.21, 0.12, "▼  Low tide", color=low, fontsize=12)
    fig.text(0.36, 0.12, "All times UTC", color=muted, fontsize=12)
    fig.text(
        0.065,
        0.06,
        f"Icelandic Coast Guard via Upperblue  ·  Retrieved {data['retrieved']}",
        color=muted,
        fontsize=9,
    )
    fig.text(
        0.065,
        0.031,
        "Astronomical predictions. Weather and wind affect sea level. Not for navigation.",
        color=muted,
        fontsize=9,
    )
    fig.savefig(output, dpi=150)


if __name__ == "__main__":
    run(__doc__, "tides.json", "tide-table.png", fetch_tides, draw)
