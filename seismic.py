"""Map one UTC day of earthquakes alongside Icelandic volcanic systems."""

import json
from datetime import UTC, date, datetime
from math import asin, cos, radians, sin, sqrt

from matplotlib.figure import Figure

from api import get
from cli import DATA, run

WEST, EAST, SOUTH, NORTH = -25, -12, 63, 67.5
INK, LAND, COAST = "#101f2b", "#233e4b", "#90a9aa"
PAPER, MUTED, QUAKE, VOLCANO = "#faf2e5", "#adbdc2", "#ff9861", "#7dd9cc"


def fetch_day(day):
    features = get("geodynamics/volcanoes/geojson")["features"]
    volcanoes = []
    for feature in features:
        lon, lat = feature["geometry"]["coordinates"][:2]
        if WEST <= lon <= EAST and SOUTH <= lat <= NORTH:
            volcanoes.append({"name": feature["properties"]["name"], "lon": lon, "lat": lat})

    quakes = []
    while True:
        page = get(
            "geodynamics/quakes",
            start_date=f"{day}T00:00:00Z",
            end_date=f"{day}T23:59:59.999Z",
            source_system="seiscomp",
            event_type="earthquake",
            sort="event_time:asc,id:asc",
            min_lon=WEST,
            max_lon=EAST,
            min_lat=SOUTH,
            max_lat=NORTH,
            fields="event_time,latitude,longitude,magnitude",
            limit=1000,
            offset=len(quakes),
        )
        for row in page["data"]:
            magnitude = row["magnitude"]
            quakes.append(
                {
                    "time": row["event_time"],
                    "lon": float(row["longitude"]),
                    "lat": float(row["latitude"]),
                    "magnitude": None if magnitude is None else float(magnitude),
                }
            )
        if len(quakes) >= page["total"]:
            break
        if not page["data"]:
            raise ValueError("Incomplete earthquake page. Please try the request again.")
    return {
        "day": day.isoformat(),
        "retrieved": datetime.now(UTC).date().isoformat(),
        "quakes": quakes,
        "volcanoes": volcanoes,
    }


def distance_km(a, b):
    lat, other = radians(a["lat"]), radians(b["lat"])
    h = sin((other - lat) / 2) ** 2
    h += cos(lat) * cos(other) * sin(radians(b["lon"] - a["lon"]) / 2) ** 2
    return 12742 * asin(sqrt(min(1, h)))


def draw(data, output):
    fig = Figure(figsize=(12, 6.5), facecolor=INK)
    ax = fig.add_axes((0.35, 0.15, 0.63, 0.76), facecolor=INK)
    ax.set(xlim=(WEST, EAST), ylim=(SOUTH, NORTH), aspect=1 / cos(radians(65)))
    ax.axis("off")
    for ring in json.loads((DATA / "coast.json").read_text()):
        ax.fill(*zip(*ring), color=LAND, ec=COAST, lw=0.7)
    for lon in range(-24, -12, 2):
        ax.axvline(lon, color=COAST, lw=0.45, alpha=0.2)
    for lat in range(64, 68):
        ax.axhline(lat, color=COAST, lw=0.45, alpha=0.2)

    quakes, volcanoes = data["quakes"], data["volcanoes"]
    for v in volcanoes:
        ax.scatter(
            v["lon"],
            v["lat"],
            s=42,
            marker="^",
            facecolor="none",
            edgecolor=VOLCANO,
            lw=1,
            zorder=3,
        )
    for q in quakes:
        ax.scatter(
            q["lon"],
            q["lat"],
            s=12 * (1 + max(0, q["magnitude"] or 0)) ** 2,
            color=QUAKE,
            alpha=0.78,
            edgecolor=INK,
            lw=0.6,
            zorder=4,
        )

    def label(y, text, size, color=PAPER, **style):
        fig.text(0.055, y, text, color=color, fontsize=size, **style)

    label(0.89, "UPPERBLUE API   /   GEODYNAMICS", 10, VOLCANO, family="monospace")
    label(0.61, "Iceland’s\nseismic day", 36, weight="bold", linespacing=1.05)
    label(0.53, date.fromisoformat(data["day"]).strftime("%d %B %Y") + "   ·   UTC", 13)
    label(0.43, f"●   {len(quakes)} earthquakes", 14, QUAKE)
    label(0.37, f"△   {len(volcanoes)} volcanic systems", 14, VOLCANO)
    peak = max(
        (q for q in quakes if q["magnitude"] is not None),
        key=lambda q: q["magnitude"],
        default=None,
    )
    if peak and volcanoes:
        near = min(volcanoes, key=lambda v: distance_km(peak, v))
        km = distance_km(peak, near)
        ax.scatter(peak["lon"], peak["lat"], s=220, facecolor="none", edgecolor=PAPER, zorder=5)
        ax.plot(
            [peak["lon"], near["lon"]],
            [peak["lat"], near["lat"]],
            color=PAPER,
            lw=0.9,
            ls=":",
            zorder=2,
        )
        ax.annotate(
            near["name"],
            (near["lon"], near["lat"]),
            xytext=(0, -14),
            textcoords="offset points",
            ha="center",
            color=PAPER,
            fontsize=9,
        )
        label(0.24, "LARGEST EARTHQUAKE", 9, MUTED, family="monospace")
        label(0.174, f"M {peak['magnitude']:.1f}   /   {peak['time'][11:16]} UTC", 16)
        label(0.12, f"{km:.0f} km from {near['name']}", 12, MUTED)
    label(
        0.035,
        f"Veðurstofa Íslands via Upperblue  ·  Retrieved {data['retrieved']}  ·  Coastline: Natural Earth",
        8,
        MUTED,
    )
    fig.savefig(output, dpi=150)


if __name__ == "__main__":
    run(__doc__, "seismic.json", "seismic-day.png", fetch_day, draw)
