import json
import urllib.parse
import urllib.request
from pathlib import Path
import os

from theme_config import BRANCHES


RUN_PROC_URL = "https://www.keyescape.com/controller/run_proc.php"


def post_run_proc(payload):
    body = urllib.parse.urlencode(payload).encode("utf-8")
    req = urllib.request.Request(
        RUN_PROC_URL,
        data=body,
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


def fetch_theme_info_list(zizum_num):
    result = post_run_proc({"t": "get_theme_info_list", "zizum_num": zizum_num})
    if not result.get("status"):
        raise RuntimeError(result.get("msg") or "get_theme_info_list failed")
    return result


def configured_themes(branch):
    themes = {}
    for theme_key, theme in branch["themes"].items():
        themes[str(theme["themeNum"])] = {
            "themeKey": theme_key,
            "themeNum": str(theme["themeNum"]),
            "themeInfoNum": str(theme["themeInfoNum"]),
            "name": theme["name"],
        }
    return themes


def normalize_actual_theme(item):
    return {
        "themeNum": str(item.get("theme_num", "")),
        "themeInfoNum": str(item.get("info_num", "")),
        "name": item.get("info_name") or "",
        "doing": str(item.get("doing", "")),
    }


def collect_inventory():
    inventory = {"branches": {}}
    changes = {"new": [], "removed": [], "changed": [], "errors": []}

    for branch_key, branch in BRANCHES.items():
        branch_info = {
            "branchKey": branch_key,
            "name": branch["name"],
            "zizumNum": str(branch["zizumNum"]),
            "themes": [],
        }
        inventory["branches"][branch_key] = branch_info

        try:
            result = fetch_theme_info_list(branch["zizumNum"])
            actual_items = [normalize_actual_theme(item) for item in result.get("data", [])]
            branch_info["actualName"] = result.get("zizum", {}).get("name") or branch["name"]
            branch_info["themes"] = actual_items
        except Exception as exc:
            changes["errors"].append(
                {
                    "branchKey": branch_key,
                    "branchName": branch["name"],
                    "zizumNum": str(branch["zizumNum"]),
                    "error": str(exc),
                }
            )
            continue

        configured_by_num = configured_themes(branch)
        actual_by_num = {item["themeNum"]: item for item in branch_info["themes"]}

        for theme_num, actual in sorted(actual_by_num.items()):
            if theme_num not in configured_by_num:
                changes["new"].append(
                    {
                        "branchKey": branch_key,
                        "branchName": branch["name"],
                        **actual,
                    }
                )

        for theme_num, configured in sorted(configured_by_num.items()):
            if theme_num not in actual_by_num:
                changes["removed"].append(
                    {
                        "branchKey": branch_key,
                        "branchName": branch["name"],
                        **configured,
                    }
                )
                continue

            actual = actual_by_num[theme_num]
            field_changes = {}
            if configured["themeInfoNum"] != actual["themeInfoNum"]:
                field_changes["themeInfoNum"] = {
                    "configured": configured["themeInfoNum"],
                    "actual": actual["themeInfoNum"],
                }
            if configured["name"] != actual["name"]:
                field_changes["name"] = {
                    "configured": configured["name"],
                    "actual": actual["name"],
                }

            if field_changes:
                changes["changed"].append(
                    {
                        "branchKey": branch_key,
                        "branchName": branch["name"],
                        "themeKey": configured["themeKey"],
                        "themeNum": theme_num,
                        "fields": field_changes,
                    }
                )

    return inventory, changes


def has_changes(changes):
    return any(changes[key] for key in ("new", "removed", "changed", "errors"))


def markdown_report(changes):
    lines = ["# 키이스케이프 테마 목록 변경 감지", ""]

    if not has_changes(changes):
        lines.append("현재 하드코딩된 테마 목록과 키이스케이프 실제 테마 목록이 일치합니다.")
        return "\n".join(lines) + "\n"

    if changes["new"]:
        lines.extend(["## 새로 발견된 테마", ""])
        for item in changes["new"]:
            lines.append(
                f"- {item['branchName']} ({item['branchKey']}): "
                f"{item['name']} / themeNum={item['themeNum']} / themeInfoNum={item['themeInfoNum']}"
            )
        lines.append("")

    if changes["removed"]:
        lines.extend(["## 실제 목록에서 사라진 테마", ""])
        for item in changes["removed"]:
            lines.append(
                f"- {item['branchName']} ({item['branchKey']}): "
                f"{item['name']} / themeKey={item['themeKey']} / themeNum={item['themeNum']}"
            )
        lines.append("")

    if changes["changed"]:
        lines.extend(["## 정보가 달라진 테마", ""])
        for item in changes["changed"]:
            field_text = ", ".join(
                f"{field}: {values['configured']} -> {values['actual']}"
                for field, values in item["fields"].items()
            )
            lines.append(
                f"- {item['branchName']} ({item['branchKey']}): "
                f"{item['themeKey']} / themeNum={item['themeNum']} / {field_text}"
            )
        lines.append("")

    if changes["errors"]:
        lines.extend(["## 확인 실패", ""])
        for item in changes["errors"]:
            lines.append(
                f"- {item['branchName']} ({item['branchKey']}): {item['error']}"
            )
        lines.append("")

    lines.extend(
        [
            "필요 작업:",
            "- `index.html`의 `branchesData` 갱신",
            "- `scripts/theme_config.py`의 `BRANCHES` 갱신",
            "- 갱신 후 `scripts/update_schedule.py` 재실행",
        ]
    )
    return "\n".join(lines) + "\n"


def write_json(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def write_github_output(changed):
    output_path = os.environ.get("GITHUB_OUTPUT")
    if not output_path:
        return
    with open(output_path, "a", encoding="utf-8") as output:
        output.write(f"has_changes={'true' if changed else 'false'}\n")


def main():
    inventory, changes = collect_inventory()
    changed = has_changes(changes)

    write_json("data/theme_inventory.json", inventory)
    write_json("data/theme_changes.json", changes)
    Path("data/theme_changes.md").write_text(markdown_report(changes), encoding="utf-8")
    write_github_output(changed)

    if changed:
        print("Theme inventory changes detected.")
    else:
        print("Theme inventory matches configured themes.")


if __name__ == "__main__":
    main()
