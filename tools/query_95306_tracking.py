import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from query95306.shipment_query import ShipmentQueryClient


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Minimal 95306 tracking query CLI for one shipment.")
    parser.add_argument("--account", required=True, help="Account key from runtime/95306_accounts.json.")
    parser.add_argument("--shipment-id", required=True, help="Plain shipment id / ydid, for example 516322603154358675.")
    parser.add_argument("--raw", action="store_true", help="Print raw tracking API response instead of normalized output.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    client = ShipmentQueryClient(args.account)
    tracking_response = client.query_tracking(args.shipment_id)
    result = tracking_response if args.raw else client.normalize_tracking(args.shipment_id, tracking_response)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
