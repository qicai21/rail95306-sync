import argparse
import json
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent


def default_db_path() -> Path:
    return ROOT_DIR / "runtime" / "95306_collection.sqlite3"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze canonical route order from stored shipment tracking routes.")
    parser.add_argument("--origin", required=True, help="Origin station name.")
    parser.add_argument("--destination", required=True, help="Destination station name.")
    parser.add_argument("--db-path", default=str(default_db_path()), help="SQLite file path.")
    parser.add_argument("--min-samples", type=int, default=1, help="Minimum completed shipment samples required.")
    return parser.parse_args()


def _load_rows(db_path: Path, origin: str, destination: str) -> list[sqlite3.Row]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT *
        FROM shipment_tracking_routes
        WHERE origin_name = ? AND destination_name = ? AND final_arrived_at IS NOT NULL
        ORDER BY final_arrived_at
        """,
        (origin, destination),
    ).fetchall()
    conn.close()
    return rows


def _route_items(row: sqlite3.Row) -> list[dict[str, Any]]:
    return json.loads(row["route_track_json"])


def _station_name(item: dict[str, Any]) -> str | None:
    value = item.get("station_name")
    if value in (None, ""):
        return None
    return str(value)


def _parse_time(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _ordered_station_sequence(items: list[dict[str, Any]], origin: str, destination: str) -> list[str]:
    observed: list[tuple[datetime, str]] = []
    fallback_names: list[str] = []
    for item in items:
        name = _station_name(item)
        if not name:
            continue
        observed_time = _parse_time(item.get("arrived_at")) or _parse_time(item.get("departed_at"))
        if observed_time is not None:
            observed.append((observed_time, name))
        else:
            fallback_names.append(name)

    observed.sort(key=lambda pair: (pair[0], pair[1]))
    names: list[str] = []
    seen: set[str] = set()

    def push(name: str | None) -> None:
        if not name:
            return
        if name in seen:
            return
        names.append(name)
        seen.add(name)

    push(origin)
    for _, name in observed:
        if name not in {origin, destination}:
            push(name)
    for name in fallback_names:
        if name not in {origin, destination}:
            push(name)
    push(destination)
    return names


def analyze_route(rows: list[sqlite3.Row], origin: str, destination: str) -> dict[str, Any]:
    station_counts: Counter[str] = Counter()
    station_arrival_counts: Counter[str] = Counter()
    station_departure_counts: Counter[str] = Counter()
    first_position_sum: dict[str, int] = defaultdict(int)
    first_position_count: Counter[str] = Counter()
    pair_order_counts: dict[tuple[str, str], int] = defaultdict(int)
    direct_edge_counts: Counter[tuple[str, str]] = Counter()

    sample_sequences: list[list[str]] = []
    for row in rows:
        items = _route_items(row)
        names = _ordered_station_sequence(items, origin, destination)
        seen_in_row: set[str] = set()
        item_map = {(_station_name(item) or ""): item for item in items if _station_name(item)}
        for idx, name in enumerate(names):
            if name not in seen_in_row:
                station_counts[name] += 1
                first_position_sum[name] += idx
                first_position_count[name] += 1
                seen_in_row.add(name)
            item = item_map.get(name, {})
            if item.get("arrived_at"):
                station_arrival_counts[name] += 1
            if item.get("departed_at"):
                station_departure_counts[name] += 1
        sample_sequences.append(names)
        for i, left in enumerate(names):
            for right in names[i + 1 :]:
                if left != right:
                    pair_order_counts[(left, right)] += 1
        for i in range(len(names) - 1):
            left = names[i]
            right = names[i + 1]
            if left != right:
                direct_edge_counts[(left, right)] += 1

    stations = sorted(station_counts.keys())
    pairwise_score: dict[str, int] = {}
    for station in stations:
        wins = 0
        losses = 0
        for other in stations:
            if other == station:
                continue
            wins += pair_order_counts.get((station, other), 0)
            losses += pair_order_counts.get((other, station), 0)
        pairwise_score[station] = wins - losses

    avg_pos: dict[str, float] = {
        station: first_position_sum[station] / first_position_count[station]
        for station in stations
        if first_position_count[station]
    }

    canonical_route = sorted(
        stations,
        key=lambda s: (
            0 if s == origin else 2 if s == destination else 1,
            avg_pos.get(s, 10**9),
            -station_counts[s],
            s,
        ),
    )

    station_summary = []
    for station in canonical_route:
        station_summary.append(
            {
                "station_name": station,
                "sample_count": station_counts[station],
                "sample_ratio": round(station_counts[station] / len(rows), 4) if rows else 0.0,
                "arrival_observed_count": station_arrival_counts[station],
                "departure_observed_count": station_departure_counts[station],
                "average_position": round(avg_pos.get(station, 0.0), 3),
                "pairwise_score": pairwise_score.get(station, 0),
            }
        )

    direct_edges = [
        {"from_station": left, "to_station": right, "count": count}
        for (left, right), count in direct_edge_counts.most_common()
    ]

    return {
        "route_group": {
            "origin": origin,
            "destination": destination,
            "sample_count": len(rows),
        },
        "canonical_route": canonical_route,
        "station_summary": station_summary,
        "top_direct_edges": direct_edges[:20],
        "sample_shipments": [
            {
                "ydid": row["ydid"],
                "car_no": row["car_no"],
                "ticketed_at": row["ticketed_at"],
                "departed_at": row["departed_at"],
                "final_arrived_at": row["final_arrived_at"],
            }
            for row in rows[:10]
        ],
    }


def main() -> int:
    args = parse_args()
    db_path = Path(args.db_path)
    rows = _load_rows(db_path, args.origin, args.destination)
    if len(rows) < args.min_samples:
        print(
            json.dumps(
                {
                    "route_group": {"origin": args.origin, "destination": args.destination},
                    "sample_count": len(rows),
                    "error": f"Not enough samples. Need at least {args.min_samples}.",
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1

    result = analyze_route(rows, args.origin, args.destination)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
