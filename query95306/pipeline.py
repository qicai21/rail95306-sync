import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from auth.session_state import SessionStateManager

from .parsing import build_shipment_projection
from .shipment_query import QueryInput, ShipmentQueryClient
from .storage import SQLiteStorage, default_db_path


@dataclass
class ShipmentCollectionSpec:
    account_key: str
    start_date: str
    end_date: str
    origin_code: str = ""
    destination_code: str = ""
    origin_keyword: str = ""
    destination_keyword: str = ""
    origin_name: str = ""
    destination_name: str = ""
    shipment_id: str = ""
    product_code: str = ""
    page_num: int = 1
    page_size: int = 50
    result_limit: int = 10


def _resolve_station_inputs(client: ShipmentQueryClient, spec: ShipmentCollectionSpec) -> tuple[str, str, dict[str, Any]]:
    origin_code = spec.origin_code
    destination_code = spec.destination_code
    station_resolution: dict[str, Any] = {}

    if spec.origin_keyword:
        station = client.resolve_station(spec.origin_keyword, exact_name=spec.origin_name or None)
        origin_code = str(station["tmism"])
        station_resolution["origin"] = station

    if spec.destination_keyword:
        station = client.resolve_station(spec.destination_keyword, exact_name=spec.destination_name or None)
        destination_code = str(station["tmism"])
        station_resolution["destination"] = station

    return origin_code, destination_code, station_resolution


def run_shipment_collection(
    spec: ShipmentCollectionSpec,
    *,
    db_path: Path | None = None,
) -> dict[str, Any]:
    storage = SQLiteStorage(db_path or default_db_path())
    client = ShipmentQueryClient(spec.account_key)
    session_manager = SessionStateManager(spec.account_key)
    origin_code, destination_code, station_resolution = _resolve_station_inputs(client, spec)
    query_input = QueryInput(
        start_date=spec.start_date,
        end_date=spec.end_date,
        destination_tmis=destination_code,
        origin_tmis=origin_code,
        product_code=spec.product_code,
        shipment_id=spec.shipment_id,
        page_num=spec.page_num,
        page_size=spec.page_size,
        result_limit=spec.result_limit,
    )

    query_run_id = storage.create_query_run(
        account_key=spec.account_key,
        query_kind="queryCargoSend",
        origin_tmis=query_input.origin_tmis,
        origin_name=station_resolution.get("origin", {}).get("hzzm"),
        destination_tmis=query_input.destination_tmis,
        destination_name=station_resolution.get("destination", {}).get("hzzm"),
        start_date=query_input.start_date,
        end_date=query_input.end_date,
        shipment_id_filter=query_input.shipment_id,
        page_size=query_input.page_size,
        query_input_json=json.dumps(asdict(query_input), ensure_ascii=False),
        station_resolution_json=json.dumps(station_resolution, ensure_ascii=False) if station_resolution else None,
    )

    try:
        send_response = client.query_send_all_pages(query_input)
        body = send_response["body"]
        data = body.get("data", {})
        storage.insert_query_run_pages(query_run_id, send_response.get("page_summaries", []))
        raw_response_id = storage.insert_raw_api_response(
            query_run_id,
            endpoint="queryCargoSend",
            page_num=None,
            http_status=send_response.get("status"),
            return_code=body.get("returnCode"),
            request_json=client.build_send_payload(query_input),
            response_json=send_response,
            headers_json=send_response.get("headers"),
        )

        for station in station_resolution.values():
            if isinstance(station, dict):
                storage.upsert_station(station)

        records = data.get("list", []) or []
        for record in records:
            shipment = build_shipment_projection(record)
            if not shipment.get("ydid"):
                continue
            storage.upsert_shipment(shipment, query_run_id, raw_response_id)
            storage.insert_shipment_snapshot(shipment["ydid"], query_run_id, raw_response_id, shipment, record)

            storage.upsert_station({"tmism": record.get("fztmism"), "hzzm": record.get("fzhzzm")})
            storage.upsert_station({"tmism": record.get("dztmism"), "hzzm": record.get("dzhzzm")})

        session_summary = session_manager.read_current_summary()
        storage.upsert_session_state(session_summary, updated_by="query_pipeline")
        storage.complete_query_run(
            query_run_id,
            status="completed",
            http_status=send_response.get("status"),
            return_code=body.get("returnCode"),
            total_records=data.get("total"),
            total_pages=data.get("pages"),
            merged_result_count=len(records),
            session_updated=bool(client.last_session_update and client.last_session_update.get("updated")),
            notes={
                "db_path": str(storage.db_path.resolve()),
                "raw_response_id": raw_response_id,
            },
        )

        return {
            "query_run_id": query_run_id,
            "db_path": str(storage.db_path.resolve()),
            "total_records": data.get("total"),
            "pages": data.get("pages"),
            "stored_shipments": len(records),
            "raw_response_id": raw_response_id,
            "session_updated": bool(client.last_session_update and client.last_session_update.get("updated")),
            "first_shipment_id": records[0].get("ydid") if records else None,
        }
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
