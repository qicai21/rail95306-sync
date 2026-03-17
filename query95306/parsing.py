import json
from typing import Any


TRANSPORT_MODE_NAMES = {
    "1": "整车运输",
    "3": "集装箱运输",
}


STAGE_SEQUENCE = (
    ("delivered", "dzjfrq", "交付"),
    ("unloading_completed", "xcwbsj", "卸车完毕"),
    ("unloading_started", "xckssj", "卸车开始"),
    ("unloading_inbound", "xcddsj", "卸车入线"),
    ("unloading_outbound", "xcdcsj", "卸车出线"),
    ("arrived", "dzsj", "到站"),
    ("departed", "fcsj", "发车"),
    ("ticketed", "zpsj", "制票"),
    ("loading_completed", "zcwbsj", "装车完毕"),
    ("loading_started", "zckssj", "装车开始"),
    ("loading_inbound", "zcddsj", "装车入线"),
    ("loading_outbound", "zcdcsj", "装车出线"),
    ("loaded", "zcrq", "装车"),
    ("accepted", "slrq", "受理"),
)


def split_container_numbers(raw_value: Any) -> list[str]:
    if raw_value is None:
        return []
    return [part.strip() for part in str(raw_value).split("/") if part.strip()]


def infer_stage(record: dict[str, Any]) -> tuple[str | None, str | None, str | None]:
    for stage_key, field_name, stage_label in STAGE_SEQUENCE:
        value = record.get(field_name)
        if value:
            return stage_key, stage_label, str(value)
    return None, None, None


def transport_mode_name(code: Any) -> str | None:
    if code is None:
        return None
    return TRANSPORT_MODE_NAMES.get(str(code))


def nullable_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def nullable_text(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)


def build_shipment_projection(record: dict[str, Any]) -> dict[str, Any]:
    stage_key, stage_label, latest_event_time = infer_stage(record)
    return {
        "ydid": nullable_text(record.get("ydid")),
        "czydid": nullable_text(record.get("czydid")),
        "transport_mode_code": nullable_text(record.get("ysfs")),
        "transport_mode_name": transport_mode_name(record.get("ysfs")),
        "car_no": nullable_text(record.get("ch")),
        "car_model": nullable_text(record.get("czcx")),
        "cargo_name": nullable_text(record.get("hzpm")),
        "cargo_count": nullable_text(record.get("hwjs")),
        "shipper_name": nullable_text(record.get("fhdwmc")),
        "consignee_name": nullable_text(record.get("shdwmc")),
        "origin_name": nullable_text(record.get("fzhzzm")),
        "origin_line_name": nullable_text(record.get("fzyxhz")),
        "destination_name": nullable_text(record.get("dzhzzm")),
        "destination_line_name": nullable_text(record.get("dzyxhz")),
        "container_no_raw": nullable_text(record.get("xh")),
        "container_numbers_json": json.dumps(split_container_numbers(record.get("xh")), ensure_ascii=False),
        "marked_weight": nullable_text(record.get("zzl")),
        "freight_fee": nullable_int(record.get("yf")),
        "accepted_at": nullable_text(record.get("slrq")),
        "loaded_at": nullable_text(record.get("zcrq")),
        "ticketed_at": nullable_text(record.get("zpsj")),
        "departed_at": nullable_text(record.get("fcsj")),
        "arrived_at": nullable_text(record.get("dzsj")),
        "delivered_at": nullable_text(record.get("dzjfrq")),
        "status_code": nullable_text(record.get("ztgjend")),
        "status_name": nullable_text(record.get("ztgjjcend")),
        "latest_stage_key": stage_key,
        "latest_stage_name": stage_label,
        "latest_event_time": latest_event_time,
        "detail_json": json.dumps(
            {
                "xqslh": record.get("xqslh"),
                "hph": record.get("hph"),
                "yjxfh": record.get("yjxfh"),
                "tyrjzsx": record.get("tyrjzsx"),
            },
            ensure_ascii=False,
        ),
        "loading_unloading_timeline_json": json.dumps(
            {
                "zcdcsj": record.get("zcdcsj"),
                "zcddsj": record.get("zcddsj"),
                "zckssj": record.get("zckssj"),
                "zcwbsj": record.get("zcwbsj"),
                "xcdcsj": record.get("xcdcsj"),
                "xcddsj": record.get("xcddsj"),
                "xckssj": record.get("xckssj"),
                "xcwbsj": record.get("xcwbsj"),
            },
            ensure_ascii=False,
        ),
        "raw_core_json": json.dumps(
            {
                "fztmism": record.get("fztmism"),
                "dztmism": record.get("dztmism"),
                "fhdwdm": record.get("fhdwdm"),
                "shdwdm": record.get("shdwdm"),
                "hph": record.get("hph"),
                "xqslh": record.get("xqslh"),
                "yjxfh": record.get("yjxfh"),
                "tyrjzsx": record.get("tyrjzsx"),
                "zffs": record.get("zffs"),
                "zfzt": record.get("zfzt"),
            },
            ensure_ascii=False,
        ),
    }
