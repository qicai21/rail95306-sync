import json
import sqlite3
from pathlib import Path
from typing import Any

from auth.account_store import ensure_runtime_dir
from auth.ticket_store import iso_now


def default_db_path() -> Path:
    return ensure_runtime_dir() / "95306_collection.sqlite3"


SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS query_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_key TEXT NOT NULL,
        query_kind TEXT NOT NULL,
        origin_tmis TEXT,
        origin_name TEXT,
        destination_tmis TEXT,
        destination_name TEXT,
        start_date TEXT NOT NULL,
        end_date TEXT NOT NULL,
        shipment_id_filter TEXT,
        page_size INTEGER NOT NULL,
        requested_at TEXT NOT NULL,
        completed_at TEXT,
        status TEXT NOT NULL,
        http_status INTEGER,
        return_code TEXT,
        total_records INTEGER,
        total_pages INTEGER,
        merged_result_count INTEGER,
        session_updated INTEGER NOT NULL DEFAULT 0,
        query_input_json TEXT NOT NULL,
        station_resolution_json TEXT,
        notes_json TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS query_run_pages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        query_run_id INTEGER NOT NULL,
        page_num INTEGER NOT NULL,
        page_size INTEGER NOT NULL,
        result_count INTEGER NOT NULL,
        total INTEGER,
        pages INTEGER,
        UNIQUE(query_run_id, page_num)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS raw_api_responses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        query_run_id INTEGER NOT NULL,
        endpoint TEXT NOT NULL,
        page_num INTEGER,
        http_status INTEGER,
        return_code TEXT,
        captured_at TEXT NOT NULL,
        request_json TEXT,
        response_json TEXT NOT NULL,
        headers_json TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS shipments (
        ydid TEXT PRIMARY KEY,
        czydid TEXT,
        transport_mode_code TEXT,
        transport_mode_name TEXT,
        car_no TEXT,
        car_model TEXT,
        cargo_name TEXT,
        cargo_count TEXT,
        shipper_name TEXT,
        consignee_name TEXT,
        origin_name TEXT,
        origin_line_name TEXT,
        destination_name TEXT,
        destination_line_name TEXT,
        container_no_raw TEXT,
        container_numbers_json TEXT,
        marked_weight TEXT,
        freight_fee INTEGER,
        accepted_at TEXT,
        loaded_at TEXT,
        ticketed_at TEXT,
        departed_at TEXT,
        arrived_at TEXT,
        delivered_at TEXT,
        status_code TEXT,
        status_name TEXT,
        latest_stage_key TEXT,
        latest_stage_name TEXT,
        latest_event_time TEXT,
        detail_json TEXT,
        loading_unloading_timeline_json TEXT,
        raw_core_json TEXT,
        latest_query_run_id INTEGER,
        latest_response_id INTEGER,
        first_seen_at TEXT NOT NULL,
        last_seen_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS shipment_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ydid TEXT NOT NULL,
        query_run_id INTEGER NOT NULL,
        source_response_id INTEGER,
        seen_at TEXT NOT NULL,
        status_code TEXT,
        status_name TEXT,
        latest_stage_key TEXT,
        latest_stage_name TEXT,
        latest_event_time TEXT,
        accepted_at TEXT,
        loaded_at TEXT,
        ticketed_at TEXT,
        departed_at TEXT,
        arrived_at TEXT,
        delivered_at TEXT,
        record_json TEXT NOT NULL,
        UNIQUE(query_run_id, ydid)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS stations (
        tmism TEXT PRIMARY KEY,
        station_name TEXT,
        pym TEXT,
        dbm TEXT,
        ljdm TEXT,
        ljqc TEXT,
        ljjc TEXT,
        cwd TEXT,
        dzm TEXT,
        hyzdmc TEXT,
        csbm TEXT,
        raw_json TEXT NOT NULL,
        last_seen_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS session_states (
        account_key TEXT PRIMARY KEY,
        ticket_file TEXT NOT NULL,
        storage_state_file TEXT NOT NULL,
        session_cookie_value TEXT,
        access_token_value TEXT,
        refresh_token_value TEXT,
        updated_at TEXT,
        updated_by TEXT,
        meta_json TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS vehicle_tracking (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ydid TEXT NOT NULL,
        car_no TEXT,
        train_group_id TEXT,
        origin_name TEXT,
        destination_name TEXT,
        cargo_name TEXT,
        trip_departure_time TEXT,
        station_name TEXT NOT NULL,
        station_tmis TEXT,
        station_dbm TEXT,
        station_sequence INTEGER,
        arrival_time TEXT,
        departure_time TEXT,
        final_arrival_time TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        UNIQUE(ydid, station_name, station_tmis)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_vehicle_tracking_group_id
    ON vehicle_tracking(train_group_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_vehicle_tracking_station_sequence
    ON vehicle_tracking(ydid, station_sequence)
    """,
    """
    CREATE TABLE IF NOT EXISTS shipment_tracking_routes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ydid TEXT NOT NULL UNIQUE,
        car_no TEXT,
        origin_name TEXT,
        destination_name TEXT,
        cargo_name TEXT,
        transport_mode TEXT,
        train_group_id TEXT,
        ticketed_at TEXT,
        departed_at TEXT,
        final_arrived_at TEXT,
        route_track_json TEXT NOT NULL,
        latest_status_json TEXT,
        current_status_summary TEXT,
        tracking_meta_json TEXT,
        raw_tracking_response_json TEXT NOT NULL,
        source_query_run_id INTEGER,
        source_response_id INTEGER,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_shipment_tracking_routes_route
    ON shipment_tracking_routes(origin_name, destination_name)
    """,
)


class SQLiteStorage:
    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or default_db_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.initialize()

    def initialize(self) -> None:
        for statement in SCHEMA_STATEMENTS:
            self.conn.execute(statement)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def create_query_run(
        self,
        *,
        account_key: str,
        query_kind: str,
        origin_tmis: str,
        origin_name: str | None,
        destination_tmis: str,
        destination_name: str | None,
        start_date: str,
        end_date: str,
        shipment_id_filter: str,
        page_size: int,
        query_input_json: str,
        station_resolution_json: str | None,
    ) -> int:
        cursor = self.conn.execute(
            """
            INSERT INTO query_runs (
                account_key, query_kind, origin_tmis, origin_name, destination_tmis, destination_name,
                start_date, end_date, shipment_id_filter, page_size, requested_at, status,
                query_input_json, station_resolution_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                account_key,
                query_kind,
                origin_tmis,
                origin_name,
                destination_tmis,
                destination_name,
                start_date,
                end_date,
                shipment_id_filter,
                page_size,
                iso_now(),
                "running",
                query_input_json,
                station_resolution_json,
            ),
        )
        self.conn.commit()
        return int(cursor.lastrowid)

    def complete_query_run(
        self,
        query_run_id: int,
        *,
        status: str,
        http_status: int | None,
        return_code: str | None,
        total_records: int | None,
        total_pages: int | None,
        merged_result_count: int | None,
        session_updated: bool,
        notes: dict[str, Any] | None,
    ) -> None:
        self.conn.execute(
            """
            UPDATE query_runs
            SET completed_at = ?, status = ?, http_status = ?, return_code = ?, total_records = ?,
                total_pages = ?, merged_result_count = ?, session_updated = ?, notes_json = ?
            WHERE id = ?
            """,
            (
                iso_now(),
                status,
                http_status,
                return_code,
                total_records,
                total_pages,
                merged_result_count,
                1 if session_updated else 0,
                json.dumps(notes, ensure_ascii=False) if notes is not None else None,
                query_run_id,
            ),
        )
        self.conn.commit()

    def insert_query_run_pages(self, query_run_id: int, page_summaries: list[dict[str, Any]]) -> None:
        for item in page_summaries:
            self.conn.execute(
                """
                INSERT OR REPLACE INTO query_run_pages (
                    query_run_id, page_num, page_size, result_count, total, pages
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    query_run_id,
                    item.get("page_num"),
                    item.get("page_size"),
                    item.get("result_count"),
                    item.get("total"),
                    item.get("pages"),
                ),
            )
        self.conn.commit()

    def insert_raw_api_response(
        self,
        query_run_id: int,
        *,
        endpoint: str,
        page_num: int | None,
        http_status: int | None,
        return_code: str | None,
        request_json: dict[str, Any] | None,
        response_json: dict[str, Any],
        headers_json: dict[str, Any] | None,
    ) -> int:
        cursor = self.conn.execute(
            """
            INSERT INTO raw_api_responses (
                query_run_id, endpoint, page_num, http_status, return_code, captured_at,
                request_json, response_json, headers_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                query_run_id,
                endpoint,
                page_num,
                http_status,
                return_code,
                iso_now(),
                json.dumps(request_json, ensure_ascii=False) if request_json is not None else None,
                json.dumps(response_json, ensure_ascii=False),
                json.dumps(headers_json, ensure_ascii=False) if headers_json is not None else None,
            ),
        )
        self.conn.commit()
        return int(cursor.lastrowid)

    def upsert_station(self, station: dict[str, Any]) -> None:
        tmism = station.get("tmism")
        if not tmism:
            return
        self.conn.execute(
            """
            INSERT INTO stations (
                tmism, station_name, pym, dbm, ljdm, ljqc, ljjc, cwd, dzm, hyzdmc, csbm, raw_json, last_seen_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(tmism) DO UPDATE SET
                station_name = excluded.station_name,
                pym = excluded.pym,
                dbm = excluded.dbm,
                ljdm = excluded.ljdm,
                ljqc = excluded.ljqc,
                ljjc = excluded.ljjc,
                cwd = excluded.cwd,
                dzm = excluded.dzm,
                hyzdmc = excluded.hyzdmc,
                csbm = excluded.csbm,
                raw_json = excluded.raw_json,
                last_seen_at = excluded.last_seen_at
            """,
            (
                str(tmism),
                station.get("hzzm"),
                station.get("pym"),
                station.get("dbm"),
                station.get("ljdm"),
                station.get("ljqc"),
                station.get("ljjc"),
                station.get("cwd"),
                station.get("dzm"),
                station.get("hyzdmc"),
                station.get("csbm"),
                json.dumps(station, ensure_ascii=False),
                iso_now(),
            ),
        )
        self.conn.commit()

    def upsert_session_state(self, summary: dict[str, Any], updated_by: str) -> None:
        self.conn.execute(
            """
            INSERT INTO session_states (
                account_key, ticket_file, storage_state_file, session_cookie_value,
                access_token_value, refresh_token_value, updated_at, updated_by, meta_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(account_key) DO UPDATE SET
                ticket_file = excluded.ticket_file,
                storage_state_file = excluded.storage_state_file,
                session_cookie_value = excluded.session_cookie_value,
                access_token_value = excluded.access_token_value,
                refresh_token_value = excluded.refresh_token_value,
                updated_at = excluded.updated_at,
                updated_by = excluded.updated_by,
                meta_json = excluded.meta_json
            """,
            (
                summary["account_key"],
                summary["ticket_file"],
                summary["storage_state_file"],
                summary.get("session_cookie_value"),
                summary.get("access_token_value"),
                summary.get("refresh_token_value"),
                summary.get("updated_at"),
                updated_by,
                json.dumps({"last_session_sync": summary.get("last_session_sync")}, ensure_ascii=False),
            ),
        )
        self.conn.commit()

    def upsert_shipment(self, shipment: dict[str, Any], query_run_id: int, source_response_id: int) -> None:
        current = self.conn.execute("SELECT first_seen_at FROM shipments WHERE ydid = ?", (shipment["ydid"],)).fetchone()
        first_seen_at = current["first_seen_at"] if current else iso_now()
        self.conn.execute(
            """
            INSERT INTO shipments (
                ydid, czydid, transport_mode_code, transport_mode_name, car_no, car_model, cargo_name, cargo_count,
                shipper_name, consignee_name, origin_name, origin_line_name, destination_name, destination_line_name,
                container_no_raw, container_numbers_json, marked_weight, freight_fee, accepted_at, loaded_at,
                ticketed_at, departed_at, arrived_at, delivered_at, status_code, status_name, latest_stage_key,
                latest_stage_name, latest_event_time, detail_json, loading_unloading_timeline_json, raw_core_json,
                latest_query_run_id, latest_response_id, first_seen_at, last_seen_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(ydid) DO UPDATE SET
                czydid = excluded.czydid,
                transport_mode_code = excluded.transport_mode_code,
                transport_mode_name = excluded.transport_mode_name,
                car_no = excluded.car_no,
                car_model = excluded.car_model,
                cargo_name = excluded.cargo_name,
                cargo_count = excluded.cargo_count,
                shipper_name = excluded.shipper_name,
                consignee_name = excluded.consignee_name,
                origin_name = excluded.origin_name,
                origin_line_name = excluded.origin_line_name,
                destination_name = excluded.destination_name,
                destination_line_name = excluded.destination_line_name,
                container_no_raw = excluded.container_no_raw,
                container_numbers_json = excluded.container_numbers_json,
                marked_weight = excluded.marked_weight,
                freight_fee = excluded.freight_fee,
                accepted_at = excluded.accepted_at,
                loaded_at = excluded.loaded_at,
                ticketed_at = excluded.ticketed_at,
                departed_at = excluded.departed_at,
                arrived_at = excluded.arrived_at,
                delivered_at = excluded.delivered_at,
                status_code = excluded.status_code,
                status_name = excluded.status_name,
                latest_stage_key = excluded.latest_stage_key,
                latest_stage_name = excluded.latest_stage_name,
                latest_event_time = excluded.latest_event_time,
                detail_json = excluded.detail_json,
                loading_unloading_timeline_json = excluded.loading_unloading_timeline_json,
                raw_core_json = excluded.raw_core_json,
                latest_query_run_id = excluded.latest_query_run_id,
                latest_response_id = excluded.latest_response_id,
                last_seen_at = excluded.last_seen_at
            """,
            (
                shipment["ydid"],
                shipment.get("czydid"),
                shipment.get("transport_mode_code"),
                shipment.get("transport_mode_name"),
                shipment.get("car_no"),
                shipment.get("car_model"),
                shipment.get("cargo_name"),
                shipment.get("cargo_count"),
                shipment.get("shipper_name"),
                shipment.get("consignee_name"),
                shipment.get("origin_name"),
                shipment.get("origin_line_name"),
                shipment.get("destination_name"),
                shipment.get("destination_line_name"),
                shipment.get("container_no_raw"),
                shipment.get("container_numbers_json"),
                shipment.get("marked_weight"),
                shipment.get("freight_fee"),
                shipment.get("accepted_at"),
                shipment.get("loaded_at"),
                shipment.get("ticketed_at"),
                shipment.get("departed_at"),
                shipment.get("arrived_at"),
                shipment.get("delivered_at"),
                shipment.get("status_code"),
                shipment.get("status_name"),
                shipment.get("latest_stage_key"),
                shipment.get("latest_stage_name"),
                shipment.get("latest_event_time"),
                shipment.get("detail_json"),
                shipment.get("loading_unloading_timeline_json"),
                shipment.get("raw_core_json"),
                query_run_id,
                source_response_id,
                first_seen_at,
                iso_now(),
            ),
        )
        self.conn.commit()

    def insert_shipment_snapshot(
        self,
        ydid: str,
        query_run_id: int,
        source_response_id: int,
        shipment: dict[str, Any],
        record_json: dict[str, Any],
    ) -> None:
        self.conn.execute(
            """
            INSERT OR IGNORE INTO shipment_snapshots (
                ydid, query_run_id, source_response_id, seen_at, status_code, status_name,
                latest_stage_key, latest_stage_name, latest_event_time, accepted_at, loaded_at,
                ticketed_at, departed_at, arrived_at, delivered_at, record_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ydid,
                query_run_id,
                source_response_id,
                iso_now(),
                shipment.get("status_code"),
                shipment.get("status_name"),
                shipment.get("latest_stage_key"),
                shipment.get("latest_stage_name"),
                shipment.get("latest_event_time"),
                shipment.get("accepted_at"),
                shipment.get("loaded_at"),
                shipment.get("ticketed_at"),
                shipment.get("departed_at"),
                shipment.get("arrived_at"),
                shipment.get("delivered_at"),
                json.dumps(record_json, ensure_ascii=False),
            ),
        )
        self.conn.commit()

    def upsert_shipment_tracking_route(
        self,
        *,
        ydid: str,
        car_no: str | None,
        origin_name: str | None,
        destination_name: str | None,
        cargo_name: str | None,
        transport_mode: str | None,
        train_group_id: str | None,
        ticketed_at: str | None,
        departed_at: str | None,
        final_arrived_at: str | None,
        route_track_json: list[dict[str, Any]],
        latest_status_json: dict[str, Any] | None,
        current_status_summary: str | None,
        tracking_meta_json: dict[str, Any] | None,
        raw_tracking_response_json: dict[str, Any],
        source_query_run_id: int | None,
        source_response_id: int | None,
    ) -> None:
        now = iso_now()
        self.conn.execute(
            """
            INSERT INTO shipment_tracking_routes (
                ydid, car_no, origin_name, destination_name, cargo_name, transport_mode, train_group_id,
                ticketed_at, departed_at, final_arrived_at, route_track_json, latest_status_json,
                current_status_summary, tracking_meta_json, raw_tracking_response_json,
                source_query_run_id, source_response_id, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(ydid) DO UPDATE SET
                car_no = excluded.car_no,
                origin_name = excluded.origin_name,
                destination_name = excluded.destination_name,
                cargo_name = excluded.cargo_name,
                transport_mode = excluded.transport_mode,
                train_group_id = excluded.train_group_id,
                ticketed_at = excluded.ticketed_at,
                departed_at = excluded.departed_at,
                final_arrived_at = excluded.final_arrived_at,
                route_track_json = excluded.route_track_json,
                latest_status_json = excluded.latest_status_json,
                current_status_summary = excluded.current_status_summary,
                tracking_meta_json = excluded.tracking_meta_json,
                raw_tracking_response_json = excluded.raw_tracking_response_json,
                source_query_run_id = excluded.source_query_run_id,
                source_response_id = excluded.source_response_id,
                updated_at = excluded.updated_at
            """,
            (
                ydid,
                car_no,
                origin_name,
                destination_name,
                cargo_name,
                transport_mode,
                train_group_id,
                ticketed_at,
                departed_at,
                final_arrived_at,
                json.dumps(route_track_json, ensure_ascii=False),
                json.dumps(latest_status_json, ensure_ascii=False) if latest_status_json is not None else None,
                current_status_summary,
                json.dumps(tracking_meta_json, ensure_ascii=False) if tracking_meta_json is not None else None,
                json.dumps(raw_tracking_response_json, ensure_ascii=False),
                source_query_run_id,
                source_response_id,
                now,
                now,
            ),
        )
        self.conn.commit()
