#!/usr/bin/env python3
"""
三井のすまい モデルルーム予約監視スクリプト
GitHub Actions で5分ごとに起動 → 内部で1分ごとに5回チェック = 実質1分間隔
"""

import os
import json
import time
import requests
from pathlib import Path
from datetime import datetime

# ============================================================
# 監視対象
# ============================================================
PROPERTIES = [
    {
        "name": "パークコート麻布十番東京",
        "url": "https://www.31sumai.com/attend/X2571/",
    },
    {
        "name": "パークコート（X1919）",
        "url": "https://www.31sumai.com/attend/X1919/",
    },
]

# 予約不可を示すテキスト（このテキストが消えたら予約開始とみなす）
UNAVAILABLE_TEXT = "ただいま予約を受け付けておりません"

# 前回の状態を保存するファイル
STATE_FILE = "reservation_state.json"

# GitHub Actionsの最短cronは5分のため、1回の実行内で1分ごとに5回チェックし実質1分間隔を実現
LOOP_COUNT = 5
LOOP_INTERVAL_SEC = 60


# ============================================================
# 状態の読み書き
# ============================================================
def load_state() -> dict:
    if Path(STATE_FILE).exists():
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {p["name"]: False for p in PROPERTIES}


def save_state(state: dict):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


# ============================================================
# 予約状況チェック
# ============================================================
def check_reservation(prop: dict) -> bool:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
        )
    }
    try:
        response = requests.get(prop["url"], headers=headers, timeout=15)
        response.raise_for_status()
        is_open = UNAVAILABLE_TEXT not in response.text
        status = "🟢 受付中！" if is_open else "🔴 受付なし"
        print(f"  [{prop['name']}] {status}")
        return is_open
    except requests.RequestException as e:
        print(f"  [{prop['name']}] ⚠️ 接続エラー: {e}")
        return False


# ============================================================
# LINE通知
# ============================================================
def send_line_notification(prop: dict):
    token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
    if not token:
        print("  ⚠️ LINE_CHANNEL_ACCESS_TOKEN が未設定です")
        return

    message = (
        f"🏠【予約受付開始】\n"
        f"{prop['name']} のモデルルーム予約受付が始まりました！\n"
        f"今すぐ予約しましょう👇\n"
        f"{prop['url']}"
    )

    try:
        resp = requests.post(
            "https://api.line.me/v2/bot/message/broadcast",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json={"messages": [{"type": "text", "text": message}]},
            timeout=10,
        )
        if resp.status_code == 200:
            print(f"  ✅ LINE通知を送信しました")
        else:
            print(f"  ❌ LINE通知失敗: {resp.status_code} {resp.text}")
    except Exception as e:
        print(f"  ❌ LINE通知エラー: {e}")


# ============================================================
# メイン処理
# ============================================================
def run_once(prev_state: dict) -> dict:
    current_state = {}

    for prop in PROPERTIES:
        is_open = check_reservation(prop)
        current_state[prop["name"]] = is_open
        was_open = prev_state.get(prop["name"], False)

        if is_open and not was_open:
            print(f"  🎉 {prop['name']} の予約開始を検知！LINE通知を送ります")
            send_line_notification(prop)
        elif not is_open and was_open:
            print(f"  [{prop['name']}] 受付終了。次回開始時に再通知します")

    return current_state


def main():
    print(f"\n{'='*50}")
    print(f"監視開始：{LOOP_COUNT}回 × {LOOP_INTERVAL_SEC}秒 = 実質{LOOP_INTERVAL_SEC}秒間隔")
    print(f"{'='*50}")

    state = load_state()

    for i in range(LOOP_COUNT):
        now = datetime.now().strftime("%H:%M:%S")
        print(f"\n--- チェック {i+1}/{LOOP_COUNT}  ({now}) ---")
        state = run_once(state)
        save_state(state)

        if i < LOOP_COUNT - 1:
            print(f"  {LOOP_INTERVAL_SEC}秒後に再チェック...")
            time.sleep(LOOP_INTERVAL_SEC)

    print(f"\n{'='*50}")
    print("全チェック完了")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
