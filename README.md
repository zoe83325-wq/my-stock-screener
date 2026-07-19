# my-stock-screener

台股選股機器人：每日台灣時間晚間9點自動掃描 AI伺服器/記憶體/科技設備/無人機航太/IC設計 概念股（39檔），
用 TWSE（上市）與 TPEx（上櫃）官方 API 抓取資料，更新收盤紀錄並用 Gmail 寄送報告。

## 選股條件

1. 帶量突破 5日或20日均線
2. 三大法人連續3日買超
3. 均線多頭排列（5MA > 20MA > 60MA 且股價站上三條均線）

三項條件皆為技術面資料整理，僅供參考，不構成投資建議。

## 設定步驟

1. 到 Google 帳號開啟兩步驟驗證（若尚未開啟），再到 https://myaccount.google.com/apppasswords
   建立一組「應用程式密碼」（App Password）。
2. 到本 repo 的 **Settings → Secrets and variables → Actions**，新增以下 Repository secrets：
   - `GMAIL_ADDRESS`：你的 Gmail 帳號
   - `GMAIL_APP_PASSWORD`：上一步取得的應用程式密碼
   - `REPORT_TO_EMAIL`：收件信箱（可跟 `GMAIL_ADDRESS` 相同）
3. 到 **Actions** 分頁，啟用 workflow（若是新 repo 需要手動啟用一次）。
4. 之後每天台灣時間 21:00 會自動執行；也可以在 Actions 頁面手動點 **Run workflow** 立即測試。

## 檔案說明

- `screener.py`：選股核心邏輯（TWSE + TPEx 官方資料源）
- `stock_list.py`：掃描的股票清單
- `run_daily.py`：每日進入點，更新 `data/closing_history.csv` 並產生 `data/latest_report.md`
- `notify_email.py`：Gmail 寄信
- `.github/workflows/daily-scan.yml`：GitHub Actions 排程設定
