import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from query95306.shipment_query import ShipmentQueryClient


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Query 95306 station suggestions and TMIS codes.")
    parser.add_argument("--account", required=True, help="Account key from runtime/95306_accounts.json.")
    parser.add_argument("--keyword", required=True, help="Station keyword, pinyin, or abbreviation, for example gqz.")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--exact-name", help="Optional exact station name to select from suggestions.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    client = ShipmentQueryClient(args.account)
    response = client.query_stations(args.keyword, limit=args.limit)
    body = response["body"]
    result: dict[str, object] = {
        "keyword": args.keyword,
        "http_status": response["status"],
        "return_code": body.get("returnCode"),
        "count": len(body.get("data", []) or []),
        "stations": body.get("data", []),
    }
    if args.exact_name:
        result["selected"] = client.resolve_station(args.keyword, exact_name=args.exact_name)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
