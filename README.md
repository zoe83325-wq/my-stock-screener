# my-stock-screener

台股選股機器人：每日台灣時間晚間9點自動掃描 AI伺服器/記憶體/科技設備/無人機航太/IC設計 概念股（39檔），
用 TWSE（上市）與 TPEx（上櫃）官方 API 抓取資料，更新收盤紀錄並用 Gmail 寄送報告。

## 選股條件

1. MA5 首次向上黃金交叉 MA10 或 MA20，交叉後3個交易日內任一天帶量（避免抓到已交叉一段時間的個股，也不強求交叉當天就放量）
2. 三大法人連續3日買超
3. 均線多頭排列（5MA > 20MA > 60MA 且股價站上三條均線）

三項條件皆為技術面資料整理，僅供參考，不構成投資建議。

## 營收動能（輔助判斷真突破/假突破）

對於符合上述三項技術面條件的個股，額外附上最新一期月營收資訊：

- 年增率（YoY）> 15% 且月增率（MoM）為正：營收動能強，較可能為真突破
- 僅其中一項成立：營收動能中等，需留意
- 兩項皆未成立：營收動能偏弱，留意假突破風險

資料源為 TWSE/TPEx 官方月營收彙總 API，僅提供最新一期（無法回溯歷史月份），
此項僅為輔助參考、**不是篩選條件**，不會影響是否入選報告。

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
- `revenue.py`：月營收成長分析（YoY/MoM），輔助判斷真突破/假突破
- `stock_list.py`：掃描的股票清單
- `run_daily.py`：每日進入點，更新 `data/closing_history.csv` 並產生 `data/latest_report.md`
- `notify_email.py`：Gmail 寄信
- `.github/workflows/daily-scan.yml`：GitHub Actions 排程設定
