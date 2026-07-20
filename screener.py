# -*- coding: utf-8 -*-
"""
台股選股核心邏輯（TWSE 上市 + TPEx 上櫃 官方 API，無爬蟲）
========================================================
邏輯：
1. MA5 首次向上黃金交叉 MA10 或 MA20，交叉後3日內任一天帶量 <- 資料源：TWSE OpenAPI / TPEx 官方個股日成交資訊
2. 三大法人連續三日買超            <- 資料源：TWSE 官方 T86 / TPEx 官方三大法人買賣明細
3. 整體線型趨勢為多頭排列          <- 資料源：TWSE OpenAPI / TPEx 官方個股日成交資訊

上市股票（TWSE）與上櫃股票（TPEx）分別使用各自的官方 API，
若某代號查不到 TWSE 資料則自動改查 TPEx。
"""

import time
import datetime as dt
from dataclasses import dataclass
from typing import Dict, List, Optional

import requests
import urllib3
import pandas as pd

from revenue import fetch_all_monthly_revenue

# TPEx（www.tpex.org.tw）的憑證鏈缺少 Subject Key Identifier 擴展，
# Python 的憑證驗證會嚴格拒絕（Windows 內建憑證庫較寬鬆才沒事），故對 TPEx 請求關閉憑證驗證。
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ----------------------------------------------------------------------------
# 參數設定
# ----------------------------------------------------------------------------

VOLUME_MULTIPLIER = 1.5      # 「帶量」定義：當日量 > 20日均量 * 此倍數
CROSSOVER_LOOKBACK_DAYS = 3  # MA5黃金交叉MA10/MA20後，允許在這幾個交易日內任一天出現帶量
CONSECUTIVE_DAYS = 3         # 三大法人連續買超天數
HISTORY_MONTHS = 3           # 每檔股票抓取的歷史價量月數
REQUEST_SLEEP = 1.0          # 對外請求時的延遲秒數（請勿調太低，避免對官方網站造成負擔）

TWSE_STOCK_DAY_ALL = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
TWSE_STOCK_DAY_URL = "https://www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY?date={date}&stockNo={stock_no}&response=json"
TWSE_T86_URL = "https://www.twse.com.tw/rwd/zh/fund/T86?date={date}&selectType=ALLBUT0999&response=json"

TPEX_STOCK_DAY_URL = "https://www.tpex.org.tw/www/zh-tw/afterTrading/tradingStock?code={code}&date={date}"
TPEX_INSTITUTIONAL_URL = "https://www.tpex.org.tw/www/zh-tw/insti/dailyTrade?date={date}&sect=AL&type=Daily"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "zh-TW,zh;q=0.9",
}


# ----------------------------------------------------------------------------
# 工具函式
# ----------------------------------------------------------------------------

def get_trading_days(end_date: dt.date, lookback: int) -> List[dt.date]:
    days = []
    d = end_date
    while len(days) < lookback:
        if d.weekday() < 5:
            days.append(d)
        d -= dt.timedelta(days=1)
    return sorted(days)


def recent_month_starts(end_date: dt.date, n_months: int) -> List[str]:
    """回傳從 end_date 所在月份往前推 n_months 個月的月份字串（YYYYMM01），由舊到新排序。"""
    months = []
    y, m = end_date.year, end_date.month
    for _ in range(n_months):
        months.append(f"{y}{m:02d}01")
        m -= 1
        if m == 0:
            m, y = 12, y - 1
    return sorted(months)


# ----------------------------------------------------------------------------
# 個股歷史價量：TWSE（上市）優先，查不到改查 TPEx（上櫃）
# ----------------------------------------------------------------------------

def fetch_all_stocks_today() -> pd.DataFrame:
    resp = requests.get(TWSE_STOCK_DAY_ALL, headers=HEADERS, timeout=10)
    resp.raise_for_status()
    return pd.DataFrame(resp.json())


def fetch_stock_history_twse(stock_no: str, months: List[str]) -> pd.DataFrame:
    frames = []
    for month_str in months:
        url = TWSE_STOCK_DAY_URL.format(date=month_str, stock_no=stock_no)
        try:
            resp = requests.get(url, headers=HEADERS, timeout=10)
            resp.raise_for_status()
            j = resp.json()
            if j.get("stat") != "OK":
                time.sleep(REQUEST_SLEEP)
                continue
            df = pd.DataFrame(j["data"], columns=j["fields"])
            frames.append(df)
        except Exception as e:
            print(f"[warn] TWSE fetch {stock_no} {month_str} failed: {e}")
        time.sleep(REQUEST_SLEEP)

    if not frames:
        return pd.DataFrame()

    full = pd.concat(frames, ignore_index=True)
    full = full.rename(columns={"日期": "date", "成交股數": "volume", "收盤價": "close"})
    full["volume"] = full["volume"].astype(str).str.replace(",", "").astype(float)
    full["close"] = full["close"].astype(str).str.replace(",", "").astype(float)
    return full[["date", "close", "volume"]]


def fetch_stock_history_tpex(stock_no: str, months: List[str]) -> pd.DataFrame:
    """TPEx回傳的成交量單位為「張」，換算成股數（*1000）以與 TWSE 單位一致。"""
    rows = []
    for month_str in months:
        date_param = f"{month_str[:4]}/{month_str[4:6]}/01"
        url = TPEX_STOCK_DAY_URL.format(code=stock_no, date=date_param)
        try:
            resp = requests.get(url, headers=HEADERS, timeout=10, verify=False)
            resp.raise_for_status()
            j = resp.json()
            data = j.get("tables", [{}])[0].get("data", [])
            for row in data:
                rows.append({
                    "date": row[0],
                    "volume": float(row[1].replace(",", "")) * 1000,
                    "close": float(row[6].replace(",", "")),
                })
        except Exception as e:
            print(f"[warn] TPEx fetch {stock_no} {month_str} failed: {e}")
        time.sleep(REQUEST_SLEEP)

    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)[["date", "close", "volume"]]


def fetch_stock_history(stock_no: str, months: List[str]) -> pd.DataFrame:
    """先查 TWSE（上市），查不到資料則改查 TPEx（上櫃）。"""
    hist = fetch_stock_history_twse(stock_no, months)
    if hist.empty:
        hist = fetch_stock_history_tpex(stock_no, months)
    return hist


# ----------------------------------------------------------------------------
# 三大法人買賣超：TWSE T86（上市）+ TPEx 三大法人買賣明細（上櫃），一次抓全市場單日資料
# ----------------------------------------------------------------------------

def fetch_t86_all(date_str: str) -> Dict[str, float]:
    """抓取指定日期（YYYYMMDD）的全上市市場三大法人買賣超日報，回傳 {代號: 三大法人買賣超股數}。"""
    url = TWSE_T86_URL.format(date=date_str)
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        j = resp.json()
    except Exception as e:
        print(f"[warn] TWSE T86 fetch {date_str} failed: {e}")
        return {}

    if j.get("stat") != "OK":
        return {}

    result = {}
    for row in j.get("data", []):
        code = row[0].strip()
        try:
            net = float(row[-1].replace(",", ""))
        except (ValueError, IndexError):
            continue
        result[code] = net
    return result


def fetch_tpex_institutional_all(date_str: str) -> Dict[str, float]:
    """抓取指定日期（YYYY/MM/DD）的全上櫃市場三大法人買賣超日報，回傳 {代號: 三大法人買賣超股數}。"""
    url = TPEX_INSTITUTIONAL_URL.format(date=date_str)
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10, verify=False)
        resp.raise_for_status()
        j = resp.json()
        rows = j.get("tables", [{}])[0].get("data", [])
    except Exception as e:
        print(f"[warn] TPEx insti fetch {date_str} failed: {e}")
        return {}

    result = {}
    for row in rows:
        code = row[0].strip()
        try:
            net = float(row[-1].replace(",", ""))
        except (ValueError, IndexError):
            continue
        result[code] = net
    return result


def get_institutional_net_buy_series(code: str, per_day: Dict[dt.date, Dict[str, float]]) -> pd.Series:
    data = {d: day_data[code] for d, day_data in per_day.items() if code in day_data}
    if not data:
        return pd.Series(dtype=float)
    s = pd.Series(data)
    s.index = pd.to_datetime(s.index)
    return s.sort_index()


# ----------------------------------------------------------------------------
# 指標計算
# ----------------------------------------------------------------------------

def check_ma_crossover_breakout(hist: pd.DataFrame) -> bool:
    """判斷近 CROSSOVER_LOOKBACK_DAYS 個交易日內，是否有 MA5 首次向上黃金交叉 MA10 或 MA20，
    且從交叉當天到今天之間，至少有一天帶量（成交量 > 20日均量 * VOLUME_MULTIPLIER）。

    只要求「交叉後幾天內帶量」而非「交叉當天必須帶量」，
    因為真正的帶量突破常常是交叉發生（趨勢轉折）之後才出現，而非同一天。
    """
    min_len = 20 + CROSSOVER_LOOKBACK_DAYS + 1
    if len(hist) < min_len:
        return False
    hist = hist.sort_values("date").reset_index(drop=True)
    hist["ma5"] = hist["close"].rolling(5).mean()
    hist["ma10"] = hist["close"].rolling(10).mean()
    hist["ma20"] = hist["close"].rolling(20).mean()
    hist["vol_ma20"] = hist["volume"].rolling(20).mean()

    above_ma10 = hist["ma5"] > hist["ma10"]
    above_ma20 = hist["ma5"] > hist["ma20"]
    # shift() 會讓布林序列的 dtype 變成 object，若不先轉回 bool，~ 會變成位元運算而非邏輯反相
    prev_above_ma10 = above_ma10.shift(1).fillna(False).astype(bool)
    prev_above_ma20 = above_ma20.shift(1).fillna(False).astype(bool)
    crossed_ma10 = above_ma10 & ~prev_above_ma10
    crossed_ma20 = above_ma20 & ~prev_above_ma20
    hist["crossed"] = crossed_ma10 | crossed_ma20
    hist["breakout_volume"] = hist["volume"] > hist["vol_ma20"] * VOLUME_MULTIPLIER

    recent = hist.iloc[-CROSSOVER_LOOKBACK_DAYS:]
    for i in range(len(recent)):
        if not bool(recent.iloc[i]["crossed"]):
            continue
        since_cross = recent.iloc[i:]
        if bool(since_cross["breakout_volume"].any()):
            return True
    return False


def check_trend_bullish(hist: pd.DataFrame) -> bool:
    if len(hist) < 61:
        return False
    hist = hist.sort_values("date").reset_index(drop=True)
    hist["ma5"] = hist["close"].rolling(5).mean()
    hist["ma20"] = hist["close"].rolling(20).mean()
    hist["ma60"] = hist["close"].rolling(60).mean()
    last = hist.iloc[-1]
    aligned = last["ma5"] > last["ma20"] > last["ma60"]
    price_above_all = last["close"] > last["ma5"] and last["close"] > last["ma20"] and last["close"] > last["ma60"]
    return bool(aligned and price_above_all)


def check_consecutive_net_buy(series: pd.Series, days: int = CONSECUTIVE_DAYS) -> bool:
    if len(series) < days:
        return False
    last_n = series.iloc[-days:]
    return bool((last_n > 0).all())


# ----------------------------------------------------------------------------
# 主流程
# ----------------------------------------------------------------------------

@dataclass
class ScreenResult:
    code: str
    name: str = ""
    date: str = ""
    close: float = 0.0
    volume: float = 0.0
    ma_crossover: bool = False
    institutional_3d: bool = False
    trend_bullish: bool = False
    revenue_yoy: Optional[float] = None
    revenue_mom: Optional[float] = None
    revenue_signal: str = ""

    @property
    def passed(self) -> bool:
        return all([self.ma_crossover, self.institutional_3d, self.trend_bullish])


def run_screener(stock_list: List[str], debug: bool = False) -> pd.DataFrame:
    """
    對 stock_list 內每檔股票跑三項條件檢查。
    回傳「每一檔」股票的結果（含當日收盤價/成交量與 passed 欄位），
    不只回傳通過條件的股票，方便同時做收盤紀錄與選股報告兩種用途。
    """
    today = dt.date.today()

    print("抓取全市場當日行情（用於股票名稱對照）...")
    all_today = fetch_all_stocks_today()
    name_map = {}
    if "Code" in all_today.columns and "Name" in all_today.columns:
        name_map = dict(zip(all_today["Code"], all_today["Name"]))

    months_needed = recent_month_starts(today, HISTORY_MONTHS)

    inst_trading_days = get_trading_days(today, CONSECUTIVE_DAYS + 5)
    print(f"抓取三大法人買賣超資料（TWSE官方 T86 + TPEx官方，共 {len(inst_trading_days)} 個交易日）...")
    per_day_institutional: Dict[dt.date, Dict[str, float]] = {}
    for d in inst_trading_days:
        twse_day = fetch_t86_all(d.strftime("%Y%m%d"))
        time.sleep(REQUEST_SLEEP)
        tpex_day = fetch_tpex_institutional_all(d.strftime("%Y/%m/%d"))
        time.sleep(REQUEST_SLEEP)
        per_day_institutional[d] = {**twse_day, **tpex_day}

    print("抓取月營收資料（TWSE + TPEx 官方，僅最新一期）...")
    revenue_map = fetch_all_monthly_revenue()

    all_results: List[ScreenResult] = []

    for code in stock_list:
        print(f"\n{'='*50}\n處理 {code} {name_map.get(code, '')}")

        hist = fetch_stock_history(code, months_needed)
        if hist.empty:
            print(f"  [錯誤] TWSE/TPEx 都抓不到 {code} 的歷史價量資料，略過")
            continue

        hist_sorted = hist.sort_values("date").reset_index(drop=True)
        last = hist_sorted.iloc[-1]
        print(f"  歷史資料筆數: {len(hist_sorted)}，最後一日: {last['date']} 收盤={last['close']} 量={last['volume']:.0f}")

        r = ScreenResult(
            code=code,
            name=name_map.get(code, ""),
            date=str(last["date"]),
            close=float(last["close"]),
            volume=float(last["volume"]),
        )
        r.ma_crossover = check_ma_crossover_breakout(hist)
        r.trend_bullish = check_trend_bullish(hist)
        print(f"  條件1 MA5黃金交叉MA10/MA20(交叉後3日內帶量): {r.ma_crossover}")
        print(f"  條件3 多頭排列:     {r.trend_bullish}")

        inst_series = get_institutional_net_buy_series(code, per_day_institutional)
        if debug:
            print(f"  三大法人買賣超 最近5日:\n{inst_series.tail(5)}")
        r.institutional_3d = check_consecutive_net_buy(inst_series)
        print(f"  條件2 三大法人連3日買超: {r.institutional_3d}")

        growth = revenue_map.get(code)
        if growth is not None:
            r.revenue_yoy = growth.yoy_pct
            r.revenue_mom = growth.mom_pct
        r.revenue_signal = growth.signal if growth is not None else "查無營收資料"
        print(f"  營收動能（僅供參考，非必要條件）: {r.revenue_signal}")

        print(f"  >>> 全部條件通過: {r.passed}")

        all_results.append(r)

    df = pd.DataFrame([r.__dict__ for r in all_results])
    if not df.empty:
        df["passed"] = df.apply(
            lambda row: bool(row["ma_crossover"] and row["institutional_3d"] and row["trend_bullish"]),
            axis=1,
        )
    return df
