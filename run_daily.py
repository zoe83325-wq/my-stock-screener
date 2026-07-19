# -*- coding: utf-8 -*-
"""每日排程進入點：跑選股掃描、更新收盤紀錄、產生報告並用 Telegram 推播。"""

import datetime as dt
import os

import pandas as pd

from screener import run_screener
from stock_list import STOCK_LIST
from notify_telegram import send_telegram_message

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
CLOSING_HISTORY_CSV = os.path.join(DATA_DIR, "closing_history.csv")
LATEST_REPORT_MD = os.path.join(DATA_DIR, "latest_report.md")


def update_closing_history(df: pd.DataFrame) -> None:
    """把今天掃描到的收盤價/成交量，以 append 方式寫進長期紀錄檔（去重：同代號同日期只留一筆）。"""
    os.makedirs(DATA_DIR, exist_ok=True)
    cols = ["date", "code", "name", "close", "volume"]
    today_records = df[cols]

    if os.path.exists(CLOSING_HISTORY_CSV):
        history = pd.read_csv(CLOSING_HISTORY_CSV, dtype={"code": str})
        combined = pd.concat([history, today_records], ignore_index=True)
        combined = combined.drop_duplicates(subset=["date", "code"], keep="last")
    else:
        combined = today_records

    combined = combined.sort_values(["date", "code"])
    combined.to_csv(CLOSING_HISTORY_CSV, index=False, encoding="utf-8-sig")
    print(f"收盤紀錄已更新：{CLOSING_HISTORY_CSV}（累計 {len(combined)} 筆）")


def build_report(df: pd.DataFrame) -> str:
    today_str = dt.date.today().strftime("%Y-%m-%d")
    passed = df[df["passed"]]

    lines = [f"台股選股報告 {today_str}", f"掃描 {len(df)} 檔（AI伺服器/記憶體/科技設備/無人機航太/IC設計）", ""]

    if passed.empty:
        lines.append("今日沒有股票同時符合三項條件（帶量突破 / 三大法人連3日買超 / 多頭排列）。")
    else:
        lines.append(f"符合全部三項條件（共 {len(passed)} 檔）：")
        for _, row in passed.iterrows():
            lines.append(f"- {row['code']} {row['name']}　收盤 {row['close']}")

    partial = df[(~df["passed"]) & (df["institutional_3d"])]
    if not partial.empty:
        lines.append("")
        lines.append("三大法人連3日買超但其他條件未到位（觀察名單）：")
        for _, row in partial.iterrows():
            lines.append(f"- {row['code']} {row['name']}　收盤 {row['close']}")

    lines.append("")
    lines.append("＊本報告僅為技術面資料整理，不構成投資建議。")
    return "\n".join(lines)


def main():
    df = run_screener(STOCK_LIST, debug=False)
    if df.empty:
        send_telegram_message("台股選股報告：今日所有股票均抓取資料失敗，請檢查資料源。")
        return

    update_closing_history(df)
    report = build_report(df)

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(LATEST_REPORT_MD, "w", encoding="utf-8") as f:
        f.write(report)

    send_telegram_message(report)
    print("\n" + report)


if __name__ == "__main__":
    main()
