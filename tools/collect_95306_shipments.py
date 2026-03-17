import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from query95306.pipeline import ShipmentCollectionSpec, run_shipment_collection
from query95306.scheduler import DEFAULT_COLLECTION_INTERVAL_SECONDS, run_collection_scheduler
from query95306.storage import default_db_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect 95306 shipment data into SQLite using the shared pipeline.")
    parser.add_argument("--account", required=True, help="Account key from runtime/95306_accounts.json.")
    parser.add_argument("--start-date", required=True, help="Query start date, for example 2026-03-12.")
    parser.add_argument("--end-date", required=True, help="Query end date, for example 2026-03-15.")
    parser.add_argument("--destination-code", default="", help="Destination TMIS code.")
    parser.add_argument("--origin-code", default="", help="Origin TMIS code.")
    parser.add_argument("--destination-keyword", default="", help="Destination station keyword.")
    parser.add_argument("--origin-keyword", default="", help="Origin station keyword.")
    parser.add_argument("--destination-name", default="", help="Exact destination station name.")
    parser.add_argument("--origin-name", default="", help="Exact origin station name.")
    parser.add_argument("--product-code", default="", help="Optional product code.")
    parser.add_argument("--shipment-id", default="", help="Optional exact shipment id.")
    parser.add_argument("--page-num", type=int, default=1)
    parser.add_argument("--page-size", type=int, default=50)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--db-path", default=str(default_db_path()), help="SQLite file path.")
    parser.add_argument("--loop", action="store_true", help="Run continuously.")
    parser.add_argument(
        "--interval-seconds",
        type=int,
        default=DEFAULT_COLLECTION_INTERVAL_SECONDS,
        help="Loop interval in seconds. Default is 1200 seconds (20 minutes).",
    )
    return parser.parse_args()


def build_spec(args: argparse.Namespace) -> ShipmentCollectionSpec:
    return ShipmentCollectionSpec(
        account_key=args.account,
        start_date=args.start_date,
        end_date=args.end_date,
        origin_code=args.origin_code,
        destination_code=args.destination_code,
        origin_keyword=args.origin_keyword,
        destination_keyword=args.destination_keyword,
        origin_name=args.origin_name,
        destination_name=args.destination_name,
        shipment_id=args.shipment_id,
        product_code=args.product_code,
        page_num=args.page_num,
        page_size=args.page_size,
        result_limit=args.limit,
    )


def main() -> int:
    args = parse_args()
    spec = build_spec(args)
    db_path = Path(args.db_path)
    if args.loop:
        return run_collection_scheduler(spec, db_path=db_path, interval_seconds=args.interval_seconds)

    result = run_shipment_collection(spec, db_path=db_path)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
