import json
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from theme_config import BRANCHES


def target_date():
    now = datetime.now(ZoneInfo("Asia/Seoul"))
    return (now + timedelta(days=6)).strftime("%Y-%m-%d")


def fetch_theme_time(date, zizum_num, theme_num):
    payload = urllib.parse.urlencode(
        {
            "t": "get_theme_time",
            "date": date,
            "zizumNum": zizum_num,
            "themeNum": theme_num,
        }
    ).encode("utf-8")

    req = urllib.request.Request(
        "https://www.keyescape.com/controller/run_proc.php",
        data=payload,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/119.0.0.0 Safari/537.36"
            ),
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
        },
        method="POST",
    )

    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=20) as response:
                result = json.loads(response.read().decode("utf-8"))
            if not isinstance(result, dict):
                raise ValueError("Invalid schedule response")
            return result
        except (OSError, ValueError):
            if attempt == 2:
                raise
            time.sleep(attempt + 1)


def normalize_slot(item):
    slot_time = f"{item.get('hh', '')}:{item.get('mm', '')}"
    if (not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", slot_time)
            or not str(item.get("num", "")).isdigit()
            or item.get("enable") not in ("Y", "N")):
        raise ValueError("Invalid schedule slot")
    return {
        "time": slot_time,
        "num": str(item.get("num", "")),
        "enable": str(item.get("enable", "")),
        "sale_txt": item.get("sale_txt") or "",
    }


def build_schedule():
    date = target_date()
    checked_at = datetime.now(ZoneInfo("Asia/Seoul")).isoformat(timespec="seconds")
    schedule = {"date": date, "checkedAt": checked_at, "branches": {}}
    errors = []

    for branch_key, branch in BRANCHES.items():
        branch_schedule = {"themes": {}, "themeStatus": {}}
        for theme_key, theme in branch["themes"].items():
            try:
                result = fetch_theme_time(date, branch["zizumNum"], theme["themeNum"])
                if result.get("status") is True and isinstance(result.get("data"), list):
                    branch_schedule["themes"][theme_key] = [
                        normalize_slot(item) for item in result["data"]
                    ]
                    state = "ready" if result["data"] else "empty"
                    branch_schedule["themeStatus"][theme_key] = {"state": state}
                elif (result.get("status") is False
                      and "예약가능시간이 아닙니다" in str(result.get("msg", ""))
                      and (opening := re.search(r"(\d{1,2}:\d{2})", result["msg"]))):
                    opening_date = datetime.fromisoformat(date) - timedelta(days=6)
                    opens_at = datetime.combine(
                        opening_date.date(), datetime.strptime(opening[1], "%H:%M").time(),
                        tzinfo=ZoneInfo("Asia/Seoul"),
                    )
                    if datetime.fromisoformat(checked_at) >= opens_at:
                        raise ValueError("API reports not open after opening time")
                    branch_schedule["themes"][theme_key] = []
                    branch_schedule["themeStatus"][theme_key] = {
                        "state": "not_open", "opensAt": opens_at.isoformat(),
                    }
                else:
                    raise ValueError(result.get("msg") or "Invalid schedule response")
            except Exception as exc:
                errors.append(f"{branch_key}/{theme_key}: {exc}")
                print(f"Failed: {branch_key}/{theme_key} - {exc}")

        schedule["branches"][branch_key] = branch_schedule

    # Never publish a broken snapshot over the last successful collection.
    if errors:
        raise RuntimeError("Schedule collection failed: " + "; ".join(errors))
    if not any(slots for branch in schedule["branches"].values() for slots in branch["themes"].values()) and not any(
        status["state"] == "not_open"
        for branch in schedule["branches"].values() for status in branch["themeStatus"].values()
    ):
        raise RuntimeError("Schedule collection returned no slots for any theme")
    return schedule


def main():
    out_path = Path("data/schedule.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    schedule = build_schedule()
    temp_path = out_path.with_suffix(".tmp")
    temp_path.write_text(
        json.dumps(schedule, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temp_path.replace(out_path)
    total = sum(
        len(slots)
        for branch in schedule["branches"].values()
        for slots in branch["themes"].values()
    )
    print(f"Success: Generated schedule.json for {schedule['date']} with {total} slots.")


if __name__ == "__main__":
    main()
