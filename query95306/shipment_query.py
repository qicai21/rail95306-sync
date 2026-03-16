import base64
import json
import http.cookiejar
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from auth.session_state import SessionStateManager
from auth.ticket_store import load_ticket_bundle, ticket_path_for_account


SEND_QUERY_URL = "https://ec.95306.cn/api/scjh/wayBillQuery/queryCargoSend"
TRACK_QUERY_URL = "https://ec.95306.cn/api/scjh/track/qeryYdgjNew"
INIT_SEND_URL = "https://ec.95306.cn/api/scjh/wayBillQuery/initCargoSend"
STATION_QUERY_URL = "https://ec.95306.cn/api/zd/vizm/queryZms"
SEND_REFERER = "https://ec.95306.cn/loading/goodsQuery"
TRACK_REFERER = "https://ec.95306.cn/ydTrickDu?prams="
STATION_CACHE_PATH = Path(__file__).resolve().parent.parent / "docs" / "95306-query-dictionaries.json"

LEGACY_STATION_MAP = {
    "新台子": "53918",
    "得胜台": "53924",
    "虎石台": "53900",
    "all": "",
}

LEGACY_SEND_STATUS_MAP = {
    "10": "待受理",
    "12": "受理通过",
    "30": "已装车",
    "35": "已制单",
    "40": "已发车",
    "60": "已到达",
    "70": "已卸车",
    "80": "货物已交付",
}

LAST_UPDATE_FIELDS = (
    "dzjfrq",
    "xcdcsj",
    "xcwbsj",
    "xckssj",
    "xcddsj",
    "dzsj",
    "fcsj",
    "zcdcsj",
    "zcwbsj",
    "zckssj",
    "zcddsj",
    "zpsj",
    "slrq",
)


@dataclass
class QueryInput:
    start_date: str
    end_date: str
    destination_tmis: str = ""
    origin_tmis: str = "51632"
    product_code: str = ""
    shipment_id: str = ""
    page_num: int = 1
    page_size: int = 50
    result_limit: int = 10


def default_query_input() -> QueryInput:
    today = date.today()
    return QueryInput(
        start_date=(today - timedelta(days=3)).isoformat(),
        end_date=today.isoformat(),
    )


def _decode_userdo(value: str) -> dict[str, Any]:
    text = value.strip()
    if not text:
        return {}
    candidates = [text]
    decoded = urllib.parse.unquote(text)
    if decoded != text:
        candidates.append(decoded)
    for candidate in candidates:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    return {}


def _build_cookie_jar(ticket_data: dict[str, Any]) -> http.cookiejar.CookieJar:
    jar = http.cookiejar.CookieJar()
    for cookie in ticket_data.get("cookies", []):
        jar.set_cookie(
            http.cookiejar.Cookie(
                version=0,
                name=cookie["name"],
                value=cookie["value"],
                port=None,
                port_specified=False,
                domain=cookie.get("domain", "ec.95306.cn"),
                domain_specified=True,
                domain_initial_dot=False,
                path=cookie.get("path", "/"),
                path_specified=True,
                secure=bool(cookie.get("secure")),
                expires=None,
                discard=True,
                comment=None,
                comment_url=None,
                rest={},
                rfc2109=False,
            )
        )
    return jar


def _extract_user_context(ticket_data: dict[str, Any]) -> dict[str, Any]:
    local_storage = ticket_data.get("local_storage", {})
    cookies = {item["name"]: item["value"] for item in ticket_data.get("cookies", [])}
    userdo_raw = cookies.get("95306-1.6.10-userdo") or local_storage.get("95306-outer-userdo", "")
    user_context = _decode_userdo(userdo_raw)
    access_token = cookies.get("95306-1.6.10-accessToken", "")
    if not access_token:
        raise ValueError("Access token not found in saved ticket.")
    return {
        "bureauDm": user_context.get("bureauDm", "02"),
        "bureauId": user_context.get("bureauId", "T00"),
        "unitId": user_context.get("unitId", ""),
        "unitName": user_context.get("unitName", ""),
        "userId": user_context.get("userId", ""),
        "userName": user_context.get("userName", ""),
        "userType": user_context.get("userType", "OUTUNIT"),
        "type": user_context.get("type", "outer"),
        "access_token": access_token,
    }


def _build_headers(ticket_data: dict[str, Any], referer: str) -> dict[str, str]:
    user_context = _extract_user_context(ticket_data)
    return {
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "Origin": "https://ec.95306.cn",
        "Referer": referer,
        "User-Agent": ticket_data.get("user_agent", "Mozilla/5.0"),
        "channel": "P",
        "bureauDm": user_context["bureauDm"],
        "bureauId": user_context["bureauId"],
        "unitId": user_context["unitId"],
        "unitName": urllib.parse.quote(user_context["unitName"]),
        "userId": user_context["userId"],
        "userName": urllib.parse.quote(user_context["userName"]),
        "userType": user_context["userType"],
        "type": user_context["type"],
        "rTrackId": uuid.uuid4().hex,
        "access_token": user_context["access_token"],
    }


def _base64_encode_tracking_id(shipment_id: str) -> str:
    encoded = shipment_id.encode("utf-8")
    for _ in range(6):
        encoded = base64.b64encode(encoded)
    return encoded.decode("utf-8")


def _latest_update_from_record(record: dict[str, Any]) -> str | None:
    for field in LAST_UPDATE_FIELDS:
        value = record.get(field)
        if value:
            return str(value)
    return None


def build_tracking_projection(shipment_id: str, tracking_response: dict[str, Any]) -> dict[str, Any]:
    body = tracking_response.get("body", {})
    data = body.get("data", {}) or {}
    fs_main = data.get("fsMain", {}) or {}
    events = data.get("gj", []) or []
    route_nodes = data.get("jlzc", []) or []
    latest_event = events[0] if events else {}

    return {
        "query_input": {
            "shipment_id": shipment_id,
            "encoded_tracking_id": _base64_encode_tracking_id(shipment_id),
        },
        "shipment": {
            "shipment_id": fs_main.get("ydid") or shipment_id,
            "car_no": fs_main.get("ch"),
            "container_no": fs_main.get("hph"),
            "cargo_name": fs_main.get("hzpm"),
            "origin_name": fs_main.get("fzhzzm"),
            "origin_tmis": fs_main.get("fztmism"),
            "origin_site_name": fs_main.get("fzyxhz"),
            "destination_name": fs_main.get("dzhzzm"),
            "destination_tmis": fs_main.get("dztmism"),
            "destination_site_name": fs_main.get("dzyxhz"),
            "shipper_name": fs_main.get("fhdwmc"),
            "consignee_name": fs_main.get("shdwmc"),
        },
        "latest_status": {
            "status_code": fs_main.get("ztgj"),
            "status_name": fs_main.get("ztgjjc"),
            "latest_event_time": latest_event.get("detail"),
            "latest_event_message": latest_event.get("message"),
            "latest_event_station": latest_event.get("operator"),
            "latest_event_station_tmis": latest_event.get("tmism"),
            "latest_event_station_dbm": latest_event.get("czdbm"),
            "latest_event_location": latest_event.get("czdz"),
            "latest_event_report_id": latest_event.get("rptid"),
        },
        "tracking_flags": data.get("gjzt", {}) or {},
        "timing": {
            "estimated_arrival_time": data.get("yjddsj"),
            "estimated_arrival_time_alt": data.get("yjddsj1"),
            "distance_remaining_km": data.get("yjddlc"),
            "use_hour": data.get("useHour"),
            "departure_date": fs_main.get("zcrq"),
            "departure_time": fs_main.get("fcsj"),
            "arrival_time": fs_main.get("dzsj"),
            "delivery_time": fs_main.get("dzjfrq"),
        },
        "events": events,
        "route_nodes": route_nodes,
        "raw_response": {
            "http_status": tracking_response.get("status"),
            "return_code": body.get("returnCode"),
            "message": body.get("msg"),
            "event_count": len(events),
            "route_node_count": len(route_nodes),
        },
    }


def _load_station_cache() -> dict[str, dict[str, Any]]:
    if not STATION_CACHE_PATH.exists():
        return {}
    payload = json.loads(STATION_CACHE_PATH.read_text(encoding="utf-8"))
    cache = payload.get("confirmed_stations", {})
    if not isinstance(cache, dict):
        return {}
    normalized = {}
    for station_name, station in cache.items():
        if not isinstance(station, dict):
            continue
        item = dict(station)
        item.setdefault("hzzm", station_name)
        normalized[station_name] = item
    return normalized


def _save_station_cache_entry(station: dict[str, Any], keyword: str | None = None) -> None:
    if not STATION_CACHE_PATH.exists():
        return
    payload = json.loads(STATION_CACHE_PATH.read_text(encoding="utf-8"))
    cache = payload.setdefault("confirmed_stations", {})
    name = str(station.get("hzzm", "")).strip()
    if not name:
        return
    updated = dict(station)
    if keyword and not updated.get("keyword"):
        updated["keyword"] = keyword
    cache[name] = updated
    STATION_CACHE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


class ShipmentQueryClient:
    def __init__(self, account_key: str):
        self.account_key = account_key
        self.ticket_path = ticket_path_for_account(account_key)
        self.ticket_data = load_ticket_bundle(self.ticket_path)
        self.session_state_manager = SessionStateManager(account_key)
        self.last_session_update: dict[str, Any] | None = None
        self.cookie_jar = _build_cookie_jar(self.ticket_data)
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cookie_jar)
        )

    def _post_json(self, url: str, payload: dict[str, Any], referer: str) -> dict[str, Any]:
        request = urllib.request.Request(
            url=url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers=_build_headers(self.ticket_data, referer),
            method="POST",
        )
        try:
            with self.opener.open(request, timeout=60) as response:
                body = response.read().decode("utf-8")
                session_updated = self.session_state_manager.sync_cookie_jar(
                    self.cookie_jar,
                    current_url=referer,
                    source=f"query:{url}",
                )
                self.last_session_update = {
                    "updated": session_updated,
                    "source_url": url,
                }
                return {
                    "status": response.status,
                    "body": json.loads(body),
                    "headers": dict(response.headers.items()),
                }
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"HTTP {exc.code} for {url}: {error_body}") from exc

    def init_send_query(self) -> dict[str, Any]:
        return self._post_json(INIT_SEND_URL, {}, SEND_REFERER)

    def query_stations(self, keyword: str, limit: int = 50, ljdm: str = "", is_no_hy: bool = True) -> dict[str, Any]:
        cache = _load_station_cache()
        keyword_lower = keyword.strip().lower()
        cached_matches = []
        for station in cache.values():
            name = str(station.get("hzzm", "")).strip()
            pym = str(station.get("pym", "")).strip().lower()
            cached_keyword = str(station.get("keyword", "")).strip().lower()
            if keyword_lower in {name.lower(), pym, cached_keyword}:
                cached_matches.append(station)
        if cached_matches:
            return {
                "status": 200,
                "body": {
                    "msg": "OK",
                    "returnCode": "00200",
                    "data": cached_matches[:limit],
                },
                "from_cache": True,
            }
        payload = {
            "q": keyword,
            "isNoHy": is_no_hy,
            "ljdm": ljdm,
            "limit": limit,
        }
        response = self._post_json(STATION_QUERY_URL, payload, SEND_REFERER)
        for station in response["body"].get("data", []) or []:
            _save_station_cache_entry(station, keyword=keyword)
        response["from_cache"] = False
        return response

    def resolve_station(self, keyword: str, exact_name: str | None = None) -> dict[str, Any]:
        response = self.query_stations(keyword)
        body = response["body"]
        data = body.get("data", []) or []
        if not data:
            raise ValueError(f"No station found for keyword: {keyword}")
        if exact_name:
            for item in data:
                if item.get("hzzm") == exact_name:
                    _save_station_cache_entry(item, keyword=keyword)
                    return item
            raise ValueError(f"Station '{exact_name}' not found in suggestions for keyword '{keyword}'")
        if len(data) == 1:
            _save_station_cache_entry(data[0], keyword=keyword)
            return data[0]
        raise ValueError(
            "Multiple stations matched keyword '%s': %s"
            % (keyword, ", ".join(str(item.get("hzzm", "")) for item in data[:10]))
        )

    def _build_send_payload(self, query_input: QueryInput) -> dict[str, Any]:
        payload = {
            "ydtbqsrq": "",
            "ydtbjzrq": "",
            "zcqsrq": query_input.start_date,
            "zcjzrq": query_input.end_date,
            "xqslh": "",
            "ydid": query_input.shipment_id,
            "fj": "",
            "dztmism": query_input.destination_tmis,
            "fztmism": query_input.origin_tmis,
            "dj": "",
            "ysfs": "",
            "shdwmc": "",
            "shdwdm": "",
            "ydztgj": "",
            "pageSize": query_input.page_size,
            "pageNum": query_input.page_num,
            "ifdzyd": "",
            "ifsetmm": "",
            "zfzt": "",
            "zffs": "",
            "dzqmjg": "",
            "ifkszlhmm": "",
            "ch": "",
            "hph": "",
            "zpsjqsrq": "",
            "zpsjjzrq": "",
            "yjxfh": "",
            "xh": "",
            "ifhnjghw": "",
            "fxbj": "",
            "zcrbjhuuid": "",
            "orderBy": "",
            "orderMode": "",
        }
        if query_input.product_code:
            payload["pm"] = query_input.product_code
        return payload

    def build_send_payload(self, query_input: QueryInput) -> dict[str, Any]:
        return self._build_send_payload(query_input)

    def query_send_legacy(self, query_input: QueryInput) -> dict[str, Any]:
        payload = self._build_send_payload(query_input)
        return self._post_json(SEND_QUERY_URL, payload, SEND_REFERER)

    def query_send_all_pages(self, query_input: QueryInput) -> dict[str, Any]:
        page_num = max(1, int(query_input.page_num))
        aggregated_records: list[dict[str, Any]] = []
        page_summaries: list[dict[str, Any]] = []
        first_response: dict[str, Any] | None = None
        total = 0
        pages = 0

        while True:
            page_input = QueryInput(
                start_date=query_input.start_date,
                end_date=query_input.end_date,
                destination_tmis=query_input.destination_tmis,
                origin_tmis=query_input.origin_tmis,
                product_code=query_input.product_code,
                shipment_id=query_input.shipment_id,
                page_num=page_num,
                page_size=query_input.page_size,
                result_limit=query_input.result_limit,
            )
            response = self.query_send_legacy(page_input)
            if first_response is None:
                first_response = response

            body = response["body"]
            data = body.get("data", {})
            total = int(data.get("total") or 0)
            pages = int(data.get("pages") or 0)
            records = data.get("list", []) or []
            aggregated_records.extend(records)
            page_summaries.append(
                {
                    "page_num": page_num,
                    "page_size": page_input.page_size,
                    "result_count": len(records),
                    "total": total,
                    "pages": pages,
                }
            )

            if not pages:
                inferred_pages = (total + page_input.page_size - 1) // page_input.page_size if page_input.page_size else 0
                pages = max(1, inferred_pages) if total else 1

            if page_num >= pages or not records:
                break
            page_num += 1

        assert first_response is not None
        merged_response = json.loads(json.dumps(first_response))
        merged_data = merged_response["body"].setdefault("data", {})
        merged_data["list"] = aggregated_records
        merged_data["total"] = total
        merged_data["pages"] = pages
        merged_data["pageNum"] = query_input.page_num
        merged_data["pageSize"] = query_input.page_size
        merged_data["size"] = len(aggregated_records)
        merged_response["page_summaries"] = page_summaries
        return merged_response

    def query_tracking(self, shipment_id: str) -> dict[str, Any]:
        encoded = _base64_encode_tracking_id(shipment_id)
        return self._post_json(
            TRACK_QUERY_URL,
            {"ydid": encoded},
            TRACK_REFERER + encoded.replace("=", "%3D"),
        )

    def normalize_tracking(self, shipment_id: str, tracking_response: dict[str, Any]) -> dict[str, Any]:
        return build_tracking_projection(shipment_id, tracking_response)

    def normalize_result(
        self,
        query_input: QueryInput,
        send_response: dict[str, Any],
        tracking_response: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        body = send_response["body"]
        data = body.get("data", {})
        records = data.get("list", [])
        primary_record = records[0] if records else {}
        tracking_data = (tracking_response or {}).get("body", {}).get("data", {})
        tracking_events = tracking_data.get("gj", [])

        normalized_shipments = []
        for record in records[: query_input.result_limit]:
            shipment_id = record.get("ydid") or record.get("czydid")
            normalized_shipments.append(
                {
                    "shipment_id": shipment_id,
                    "origin": record.get("fzhzzm"),
                    "destination": record.get("dzhzzm"),
                    "shipment_status": record.get("ztgjjcend")
                    or LEGACY_SEND_STATUS_MAP.get(str(record.get("ztgjend"))),
                    "last_update_time": _latest_update_from_record(record),
                    "raw_status_code": record.get("ztgjend"),
                }
            )

        selected_tracking_last_update = tracking_events[0].get("detail") if tracking_events else None
        selected_tracking_message = tracking_events[0].get("message") if tracking_events else None
        selected_tracking_status = None
        if tracking_events:
            selected_tracking_status = tracking_data.get("fsMain", {}).get("ztgjjc")
        elif tracking_data.get("fsMain"):
            selected_tracking_status = tracking_data["fsMain"].get("ztgjjc")

        return {
            "query_input": asdict(query_input),
            "shipment_id": primary_record.get("ydid") or primary_record.get("czydid"),
            "origin": primary_record.get("fzhzzm"),
            "destination": primary_record.get("dzhzzm"),
            "shipment_status": selected_tracking_status
            or primary_record.get("ztgjjcend")
            or LEGACY_SEND_STATUS_MAP.get(str(primary_record.get("ztgjend"))),
            "last_update_time": selected_tracking_last_update or _latest_update_from_record(primary_record),
            "shipments": normalized_shipments,
            "raw_response": {
                "http_status": send_response["status"],
                "return_code": body.get("returnCode"),
                "total": data.get("total", 0),
                "result_count": len(records),
                "returned_shipments": len(normalized_shipments),
                "result_limit": query_input.result_limit,
                "first_result_keys": sorted(primary_record.keys())[:20] if primary_record else [],
                "tracking_http_status": tracking_response.get("status") if tracking_response else None,
                "tracking_event_count": len(tracking_events),
                "latest_tracking_message": selected_tracking_message,
                "page_summaries": send_response.get("page_summaries", []),
            },
            "mapping_notes": {
                "status_code_map": LEGACY_SEND_STATUS_MAP,
                "station_map_from_legacy_code": LEGACY_STATION_MAP,
                "last_update_time_rule": list(LAST_UPDATE_FIELDS),
                "station_lookup": {
                    "url": STATION_QUERY_URL,
                    "request_fields": {
                        "q": "站名/拼音检索词",
                        "isNoHy": "是否排除货运站过滤",
                        "ljdm": "路局代码过滤",
                        "limit": "候选上限",
                    },
                    "response_fields": {
                        "tmism": "站点TMIS编码",
                        "hzzm": "站名",
                        "pym": "拼音码",
                        "dbm": "电报码",
                        "ljdm": "路局代码",
                        "ljqc": "路局全称",
                        "ljjc": "路局简称",
                    },
                },
                "tracking_fields": {
                    "fsMain.ztgjjc": "追踪主状态",
                    "gj[0].message": "最新追踪消息",
                    "gj[0].detail": "最新追踪时间",
                },
            },
        }


def save_report(path: Path, payload: dict[str, Any]) -> Path:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
