# -*- coding: utf-8 -*-
"""月營收成長分析：用來判斷技術面突破是否有基本面（營收動能）支撐。

資料源：TWSE / TPEx 官方每月營收彙總 API，兩邊皆只提供「最新一期」全市場資料，
無法回溯查詢歷史月份，因此本模組僅用最新一期的年增率（YoY）與月增率（MoM）判斷。
"""

from dataclasses import dataclass
from typing import Dict, Optional

import requests
import urllib3

# 原因同 screener.py：TPEx 憑證鏈缺少 Subject Key Identifier 擴展，需關閉憑證驗證。
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

TWSE_MONTHLY_REVENUE_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap05_L"
TPEX_MONTHLY_REVENUE_URL = "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap05_O"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "zh-TW,zh;q=0.9",
}

REVENUE_YOY_THRESHOLD = 15.0  # 年增率門檻（%），高於此值視為「顯著成長」


@dataclass
class RevenueGrowth:
    data_month: str = ""  # 資料年月（民國年，例如 "11506" = 115年6月）
    yoy_pct: Optional[float] = None
    mom_pct: Optional[float] = None

    @property
    def has_data(self) -> bool:
        return self.yoy_pct is not None

    @property
    def yoy_significant(self) -> bool:
        return self.yoy_pct is not None and self.yoy_pct > REVENUE_YOY_THRESHOLD

    @property
    def mom_positive(self) -> bool:
        return self.mom_pct is not None and self.mom_pct > 0

    @property
    def signal(self) -> str:
        """給報告用的簡短判讀文字，協助判斷真突破/假突破。"""
        if not self.has_data:
            return "查無營收資料"

        detail = f"YoY {self.yoy_pct:+.1f}% / MoM {self.mom_pct:+.1f}%"
        if self.yoy_significant and self.mom_positive:
            return f"營收動能強（{detail}）→ 較可能為真突破"
        if self.yoy_significant or self.mom_positive:
            return f"營收動能中等（{detail}）→ 需留意"
        return f"營收動能偏弱（{detail}）→ 留意假突破風險"


def _parse_row(row: dict) -> Optional[RevenueGrowth]:
    def _to_float(key: str) -> Optional[float]:
        try:
            return float(row[key])
        except (KeyError, ValueError, TypeError):
            return None

    yoy = _to_float("營業收入-去年同月增減(%)")
    mom = _to_float("營業收入-上月比較增減(%)")
    if yoy is None and mom is None:
        return None
    return RevenueGrowth(data_month=str(row.get("資料年月", "")), yoy_pct=yoy, mom_pct=mom)


def fetch_all_monthly_revenue() -> Dict[str, RevenueGrowth]:
    """抓取全市場（上市+上櫃）最新一期月營收，回傳 {股票代號: RevenueGrowth}。"""
    result: Dict[str, RevenueGrowth] = {}

    for url, verify in ((TWSE_MONTHLY_REVENUE_URL, True), (TPEX_MONTHLY_REVENUE_URL, False)):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15, verify=verify)
            resp.raise_for_status()
            rows = resp.json()
        except Exception as e:
            print(f"[warn] 月營收資料抓取失敗 ({url}): {e}")
            continue

        for row in rows:
            code = str(row.get("公司代號", "")).strip()
            if not code:
                continue
            growth = _parse_row(row)
            if growth is not None:
                result[code] = growth

    return result
