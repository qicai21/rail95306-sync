import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from auth.preflight_95306 import build_preflight_report, format_preflight_summary, write_preflight_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check whether local 95306 accounts and ticket files are ready for worker startup.")
    parser.add_argument("--strict", action="store_true", help="Fail if any configured account is not fully initialized.")
    parser.add_argument("--status", action="store_true", help="Print current account initialization status.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_preflight_report(strict=args.strict)
    report_path = write_preflight_report(report)
    print(format_preflight_summary(report))
    print("preflight report: %s" % report_path)
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
