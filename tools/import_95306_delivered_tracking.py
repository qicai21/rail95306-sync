import argparse
import json
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from query95306.parsing import transport_mode_name
from query95306.shipment_query import QueryInput, ShipmentQueryClient
from query95306.storage import SQLiteStorage, default_db_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import delivered 95306 tracking data into SQLite.")
    parser.add_argument("--account", required=True, help="Account key from runtime/95306_accounts.json.")
    parser.add_argument("--start-date", required=True, help="Shipment query start date.")
    parser.add_argument("--end-date", required=True, help="Shipment query end date.")
    parser.add_argument("--origin-code", required=True, help="Origin TMIS code.")
    parser.add_argument("--destination-code", required=True, help="Destination TMIS code.")
    parser.add_argument("--db-path", default=str(default_db_path()), help="SQLite file path.")
    parser.add_argument("--limit", type=int, default=0, help="Optional limit for test runs.")
    parser.add_argument("--sleep-seconds", type=float, default=0.0, help="Sleep interval between tracking requests.")
    parser.add_argument("--skip-existing", action="store_true", help="Skip shipments already present in shipment_tracking_routes.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    client = ShipmentQueryClient(args.account)
    storage = SQLiteStorage(Path(args.db_path))

    query_input = QueryInput(
        start_date=args.start_date,
        end_date=args.end_date,
        origin_tmis=args.origin_code,
        destination_tmis=args.destination_code,
        page_num=1,
        page_size=50,
        result_limit=10,
    )
    query_run_id = storage.create_query_run(
        account_key=args.account,
        query_kind="trackingImportDelivered",
        origin_tmis=args.origin_code,
        origin_name=None,
        destination_tmis=args.destination_code,
        destination_name=None,
        start_date=args.start_date,
        end_date=args.end_date,
        shipment_id_filter="",
        page_size=query_input.page_size,
        query_input_json=json.dumps(
            {
                "kind": "trackingImportDelivered",
                "start_date": args.start_date,
                "end_date": args.end_date,
                "origin_code": args.origin_code,
                "destination_code": args.destination_code,
                "limit": args.limit,
            },
            ensure_ascii=False,
        ),
        station_resolution_json=None,
    )

    try:
        send_response = client.query_send_all_pages(query_input)
        body = send_response["body"]
        data = body.get("data", {})
        records = data.get("list", []) or []
        storage.insert_query_run_pages(query_run_id, send_response.get("page_summaries", []))

        delivered_records = [record for record in records if record.get("dzjfrq")]

        existing_ids: set[str] = set()
        if args.skip_existing:
            rows = storage.conn.execute("SELECT ydid FROM shipment_tracking_routes").fetchall()
            existing_ids = {str(row["ydid"]) for row in rows}
            delivered_records = [record for record in delivered_records if str(record.get("ydid") or "").strip() not in existing_ids]

        if args.limit > 0:
            delivered_records = delivered_records[: args.limit]

        imported = 0
        failed: list[dict[str, str]] = []
        for record in delivered_records:
            shipment_id = str(record.get("ydid") or "").strip()
            if not shipment_id:
                continue
            try:
                tracking_response = client.query_tracking(shipment_id)
                tracking_body = tracking_response.get("body", {})
                raw_response_id = storage.insert_raw_api_response(
                    query_run_id,
                    endpoint="qeryYdgjNew",
                    page_num=None,
                    http_status=tracking_response.get("status"),
                    return_code=tracking_body.get("returnCode"),
                    request_json={"shipment_id": shipment_id},
                    response_json=tracking_response,
                    headers_json=tracking_response.get("headers"),
                )
                normalized = client.normalize_tracking(shipment_id, tracking_response)
                transport_mode = transport_mode_name(record.get("ysfs")) or str(record.get("ysfs") or "")
                final_arrived_at = record.get("dzsj")
                storage.upsert_shipment_tracking_route(
                    ydid=shipment_id,
                    car_no=record.get("ch"),
                    origin_name=record.get("fzhzzm"),
                    destination_name=record.get("dzhzzm"),
                    cargo_name=record.get("hzpm"),
                    transport_mode=transport_mode,
                    train_group_id=None,
                    ticketed_at=record.get("zpsj"),
                    departed_at=record.get("fcsj") or normalized.get("tracking_table_preview", {}).get("departure_time"),
                    final_arrived_at=final_arrived_at,
                    route_track_json=normalized.get("route_track", []),
                    latest_status_json=normalized.get("latest_status"),
                    current_status_summary=normalized.get("current_status_summary"),
                    tracking_meta_json={
                        "derived_status": normalized.get("derived_status"),
                        "estimated_arrival_time": normalized.get("timing", {}).get("estimated_arrival_time"),
                        "event_count": normalized.get("raw_response", {}).get("event_count"),
                        "route_node_count": normalized.get("raw_response", {}).get("route_node_count"),
                    },
                    raw_tracking_response_json=tracking_response,
                    source_query_run_id=query_run_id,
                    source_response_id=raw_response_id,
                )
                imported += 1
                if args.sleep_seconds > 0:
                    time.sleep(args.sleep_seconds)
            except Exception as exc:
                failed.append({"shipment_id": shipment_id, "error": str(exc)})

        storage.complete_query_run(
            query_run_id,
            status="completed" if not failed else "completed_with_errors",
            http_status=send_response.get("status"),
            return_code=body.get("returnCode"),
            total_records=len(delivered_records),
            total_pages=data.get("pages"),
            merged_result_count=imported,
            session_updated=bool(client.last_session_update and client.last_session_update.get("updated")),
            notes={
                "matched_delivered_records": len(delivered_records),
                "imported": imported,
                "failed": failed,
            },
        )
        print(
            json.dumps(
                {
                    "query_run_id": query_run_id,
                    "matched_delivered_records": len(delivered_records),
                    "imported": imported,
                    "failed_count": len(failed),
                    "failed": failed[:20],
                    "db_path": str(storage.db_path.resolve()),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    except Exception as exc:
        storage.complete_query_run(
            query_run_id,
            status="failed",
            http_status=None,
            return_code=None,
            total_records=None,
            total_pages=None,
            merged_result_count=None,
            session_updated=bool(client.last_session_update and client.last_session_update.get("updated")),
            notes={"error": str(exc)},
        )
        raise
    finally:
        storage.close()


if __name__ == "__main__":
    raise SystemExit(main())
