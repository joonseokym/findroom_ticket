import json
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo


BRANCHES = {
    "MEMORY": {
        "zizumNum": "18",
        "themes": {
            "EDDY": {"themeNum": "57"},
            "STEVE": {"themeNum": "58"},
            "BOB": {"themeNum": "59"},
        },
    },
    "WHOSTHERE": {
        "zizumNum": "23",
        "themes": {
            "AYAKO": {"themeNum": "71"},
            "TUTU": {"themeNum": "69"},
            "GOEROK": {"themeNum": "70"},
        },
    },
    "GANGNAM_ST": {
        "zizumNum": "22",
        "themes": {
            "MONEY_ESTATE": {"themeNum": "65"},
            "MY_ROOM": {"themeNum": "66"},
            "NOSTALGIA": {"themeNum": "67"},
        },
    },
    "LOGIN_1": {
        "zizumNum": "19",
        "themes": {
            "MONEY_PKG": {"themeNum": "60"},
            "FOR_FREE": {"themeNum": "63"},
        },
    },
    "LOGIN_2": {
        "zizumNum": "20",
        "themes": {
            "GENTLE_MON": {"themeNum": "64"},
            "BACKTO": {"themeNum": "61"},
        },
    },
    "WOOJU": {
        "zizumNum": "16",
        "themes": {
            "WANNA": {"themeNum": "56"},
            "US": {"themeNum": "55"},
        },
    },
    "GANGNAM_OREUM": {
        "zizumNum": "14",
        "themes": {
            "ANGELIO": {"themeNum": "51"},
            "NED": {"themeNum": "48"},
        },
    },
}


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
            "endDay": "0",
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

    with urllib.request.urlopen(req, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def normalize_slot(item):
    return {
        "time": f"{item.get('hh', '')}:{item.get('mm', '')}",
        "num": str(item.get("num", "")),
        "enable": str(item.get("enable", "")),
        "sale_txt": item.get("sale_txt") or "",
    }


def build_schedule():
    date = target_date()
    schedule = {"date": date, "branches": {}}

    for branch_key, branch in BRANCHES.items():
        branch_schedule = {"themes": {}}
        for theme_key, theme in branch["themes"].items():
            try:
                result = fetch_theme_time(date, branch["zizumNum"], theme["themeNum"])
                if result.get("status") and result.get("data"):
                    branch_schedule["themes"][theme_key] = [
                        normalize_slot(item) for item in result["data"]
                    ]
                else:
                    branch_schedule["themes"][theme_key] = []
                    print(f"No schedule: {branch_key}/{theme_key} - {result.get('msg', '')}")
            except Exception as exc:
                branch_schedule["themes"][theme_key] = []
                print(f"Failed: {branch_key}/{theme_key} - {exc}")

        schedule["branches"][branch_key] = branch_schedule

    return schedule


def main():
    out_path = Path("data/schedule.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    schedule = build_schedule()
    out_path.write_text(
        json.dumps(schedule, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    total = sum(
        len(slots)
        for branch in schedule["branches"].values()
        for slots in branch["themes"].values()
    )
    print(f"Success: Generated schedule.json for {schedule['date']} with {total} slots.")


if __name__ == "__main__":
    main()
