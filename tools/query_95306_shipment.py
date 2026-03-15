import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from query95306.shipment_query import QueryInput, ShipmentQueryClient, default_query_input


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Minimal 95306 shipment query PoC with automatic pagination.")
    parser.add_argument("--account", required=True, help="Account key from runtime/95306_accounts.json.")
    parser.add_argument("--start-date", help="Query start date, for example 2026-03-12.")
    parser.add_argument("--end-date", help="Query end date, for example 2026-03-15.")
    parser.add_argument("--destination-code", default="", help="Destination TMIS code, for example 53918.")
    parser.add_argument("--origin-code", default="51632", help="Origin TMIS code. Legacy default is 51632.")
    parser.add_argument("--destination-keyword", default="", help="Destination station lookup keyword, for example xtz.")
    parser.add_argument("--origin-keyword", default="", help="Origin station lookup keyword, for example gqz.")
    parser.add_argument("--destination-name", default="", help="Exact destination station name to select from suggestions.")
    parser.add_argument("--origin-name", default="", help="Exact origin station name to select from suggestions.")
    parser.add_argument("--product-code", default="", help="Optional product code. Leave empty to match the current page payload.")
    parser.add_argument("--shipment-id", default="", help="Optional shipment id / ydid filter.")
    parser.add_argument("--page-num", type=int, default=1)
    parser.add_argument("--page-size", type=int, default=50)
    parser.add_argument("--limit", type=int, default=10, help="Number of normalized shipment rows to print.")
    parser.add_argument("--skip-track", action="store_true", help="Skip the tracking detail request.")
    parser.add_argument("--single-page", action="store_true", help="Only request one page instead of following all pages.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    defaults = default_query_input()
    client = ShipmentQueryClient(args.account)

    origin_code = args.origin_code
    destination_code = args.destination_code
    station_resolution = {}

    if args.origin_keyword:
        resolved_origin = client.resolve_station(args.origin_keyword, exact_name=args.origin_name or None)
        origin_code = str(resolved_origin["tmism"])
        station_resolution["origin"] = resolved_origin
    elif args.origin_name:
        resolved_origin = client.resolve_station(args.origin_name, exact_name=args.origin_name)
        origin_code = str(resolved_origin["tmism"])
        station_resolution["origin"] = resolved_origin

    if args.destination_keyword:
        resolved_destination = client.resolve_station(args.destination_keyword, exact_name=args.destination_name or None)
        destination_code = str(resolved_destination["tmism"])
        station_resolution["destination"] = resolved_destination
    elif args.destination_name:
        resolved_destination = client.resolve_station(args.destination_name, exact_name=args.destination_name)
        destination_code = str(resolved_destination["tmism"])
        station_resolution["destination"] = resolved_destination

    query_input = QueryInput(
        start_date=args.start_date or defaults.start_date,
        end_date=args.end_date or defaults.end_date,
        destination_tmis=destination_code,
        origin_tmis=origin_code,
        product_code=args.product_code,
        shipment_id=args.shipment_id,
        page_num=args.page_num,
        page_size=args.page_size,
        result_limit=args.limit,
    )
    send_response = client.query_send_legacy(query_input) if args.single_page else client.query_send_all_pages(query_input)

    tracking_response = None
    if not args.skip_track:
        records = send_response["body"].get("data", {}).get("list", [])
        tracking_target = args.shipment_id or (records[0].get("ydid") if records else "")
        if tracking_target:
            tracking_response = client.query_tracking(tracking_target)

    result = client.normalize_result(query_input, send_response, tracking_response)
    if station_resolution:
        result["station_resolution"] = station_resolution
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
