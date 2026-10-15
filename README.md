# Agent Learning Radar

為具影像 AI 開發經驗、初步理解 LLM 的工程師設計的繁體中文學習網站。

- 研究基準：**2026-10-15**；12 週、每週 6–8 小時，以個人知識與研究助理為實作主線。
- 每週皆有目標、概念、步驟、完成條件、常見失敗與官方教材。
- 20 個官方來源的技術雷達、9 個框架／架構選項的比較、來源健康狀態。
- 產品／分類／類型／日期／關鍵字篩選、收藏、進度保存、JSON 備份及 RSS。
- 純靜態前端與 Python 3.12 標準函式庫。收集、測試、建置均不需付費 LLM API、套件安裝或第三方資料庫。

預定網站：<https://bobtsengusig.github.io/agent-learning-radar/>  
RSS：<https://bobtsengusig.github.io/agent-learning-radar/feed.xml>

## 本機使用

在專案根目錄執行（Windows 若使用 Python Launcher，可將 `python` 改為 `py -3.12`）：

```sh
python -m unittest discover -s tests -v
python scripts/radar.py validate
python scripts/build.py
python -m http.server 8765 --bind 127.0.0.1 --directory dist
```

開啟 <http://127.0.0.1:8765/>。`dist/` 亦可整份複製到任何靜態主機，檔案採相對路徑，支援 GitHub Pages 的專案子路徑。直接開啟 `dist/index.html` 也能閱讀與搜尋，但瀏覽器對本機檔案的儲存支援各異，建議使用 HTTP 預覽。

手動收集官方資料：

```sh
python scripts/radar.py collect --weekly
python scripts/build.py
```

本機沒有 GitHub token 也能讀取公開來源，但會受匿名 API 限流。若需要提高額度，可在環境變數提供 `GITHUB_TOKEN`；不要把 token 寫入檔案或提交至專案。Actions 自動使用短效的 `github.token`。

## 首次發布

1. 建立公開專案並保留 `main` 分支。
2. 在 **Settings → Pages → Build and deployment → Source** 選擇 **GitHub Actions**。
3. 上傳本專案原始碼（包含 `.github/workflows/` 與 `data/radar.json`）。
4. **Actions → Update radar and deploy Pages** 會因 `main` 更新而執行；也可按 **Run workflow** 手動啟動。
5. 確認 `collect-build` 與 `deploy` 皆成功，點選 deployment 的 `page_url` 驗證正式網站。

僅公開儲存庫不會自動啟用 Pages。若 GitHub 顯示 Actions 或環境核准要求，依該帳號／組織既有設定完成。此專案不會自動修改帳號安全設定。

## 更新機制

`.github/workflows/update.yml` 在每日 **00:17 UTC＝08:17 台北時間**執行，另支援 `workflow_dispatch` 與 `main` 的程式／資料更新。GitHub 排程可能延後或略過；時間不是 SLA。

同一工作流程依序執行測試、收集、驗證、產生網站、提交資料與部署。因此即使使用 `GITHUB_TOKEN` 的資料提交不觸發另一輪 workflow，仍會部署本次資料；也不會因更新資料而無限遞迴。

週報以**台北時間前一個完整週**為單位，保存歷史週報。首次執行會回溯目前資料涵蓋的完整週；錯過週一後會於下次成功執行補齊。晚到的消息會更新對應歷史週報；未變更的週報保留原本產生時間。手動的 `weekly` 輸入保留作操作提示；每次收集都會檢查並補齊週報。

RSS 的每個 item 對應一份週報，GUID 為固定週次；修訂週報不產生重複 GUID。沒有發布日期的消息依首次發現時間歸週並明確標示。

## 來源設定與資料格式

`sources.json` 集中管理以下來源：OpenAI、Claude、Gemini、Transformers、OpenAI Agents SDK、Claude Agent SDK、LangGraph、Deep Agents、Google ADK、Microsoft Agent Framework、Pydantic AI、CrewAI、MCP、A2A、LlamaIndex、Qdrant、Langfuse、Promptfoo、Ollama、vLLM。

- `github`：GitHub Releases，包含官方標示的 prerelease、排除 draft；每來源最多 6 頁、每頁 100 筆。
- `atom`：RSS／Atom 官方發布消息。
- `changelog`：官方日期標題頁。OpenAI 使用其官方 `.md` 版本；Claude、Gemini 解析 HTML 日期標題。原文連結仍指向可閱讀的官方更新頁。

每則消息包含 `id`、`source_id`、`product`、`category`、`title`、`url`、`version`、`release_type`、`published_at`、`first_seen_at`、`updated_at`、`revision_count`、`excerpt`、`source_body_hash` 及 `content_hash`。

- 穩定 ID 由來源與官方 release ID、feed ID 或日期組成。相同 ID 的修訂更新既有紀錄；首次發現時間保留。
- HTML 更新頁以「同日消息彙整」為一筆，不保證每個功能獨立成一筆。日期缺失保存為 `null`。
- `source_body_hash` 使用完整標準化來源文字計算，仍可辨識短摘錄以外的修訂；不保存完整文章內容。
- 短摘錄最多 24 個空白分隔詞、180 字元，附原始連結。以原文為準，沒有 AI 翻譯或影響分析。
- 首次收集涵蓋執行時往前 90 日中可取得的消息；之後保留已收集歷史。來源可能只保留部分消息，達分頁上限會在涵蓋範圍註明。這不是完整年度新聞資料庫。
- 版本狀態依官方欄位判斷；框架比較、成熟度與課程建議為人工編輯內容，不由發布頻率推論。

`data/radar.json` 為公開資料，`schema_version` 為 1。每來源健康狀態分開記錄最近嘗試、最近成功、錯誤及涵蓋範圍。

## 故障與恢復

- **部分來源失敗：**其舊資料保留，其他來源繼續更新；網站顯示異常。下載 Actions 的 `collection-status` artifact 查看細節。
- **全部來源失敗：**工作流程失敗，保留上一版資料及網站；本次診斷仍上傳 artifact（保存 7 天）。
- **資料驗證失敗：**不提交新資料、不部署；修復來源或解析器後手動重跑。
- **HTML 格式變更：**若找不到日期，視為解析失敗，避免把空資料當成更新成功。新增固定樣本測試後再修復解析器。
- **限流：**尊重短時間 `Retry-After` 並有限次重試；超過 30 秒的限流等待延到下次執行，避免佔用 runner。
- **超過 48 小時未成功更新：**頁面依使用者目前時間顯示警示。檢查 Actions 是否啟用、最近執行結果及資料時間。
- **排程停用：**公開專案 60 天無活動時 GitHub 可能停用 schedule。在 Actions 選擇工作流程 → Enable workflow，再 Run workflow。參見 [官方限制](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)。不製造空提交來繞過限制。
- **回退：**在 GitHub 將有問題的程式變更 revert，使用上次有效的 `data/radar.json`，再重跑工作流程。部署失敗不會取代仍可用的上一版。

## 個人資料、權限與維護

進度與收藏只存在瀏覽器的 `localStorage`。不含登入、追蹤分析、外部字型、廣告或雲端同步。備份以 `schema_version: 1`、`completed_weeks` 與 `bookmarks` 三個欄位保存；可匯出／匯入 JSON。有效匯入會取代目前資料，匯入前版本留存在 `agent-learning-radar:personal:v1:before-import` 供復原；無效檔案不改變資料。

公開網頁與資料檔**不可放入私人文件、金鑰或個人進度**。外部文字以跳脫後的 HTML 或 `textContent` 顯示，連結限制為 HTTPS；來源內容不會作為程式執行。GitHub token 僅傳給 `api.github.com`，跨主機重新導向移除授權標頭。

CI 的 PR 檢查只有讀取權限；只有正式更新工作有資料寫入權限，部署工作僅有 `pages: write` 與 `id-token: write`。官方 Actions 以已查核的 commit SHA 固定。更新 Actions 時應查核官方 release、版本支援與權限，測試後再變更。

課程在 `content/roadmap.json`，框架比較在 `content/frameworks.json`；修改這些內容時，查核官方文件並更新基準或對應查核日期。`content/settings.json` 包含網站網址、分類與儲存庫；fork 後請修改 URL。

本網站不執行付費 LLM API。課程實作呼叫模型、embedding 或評估模型可能產生費用；可先用模擬模型練習流程，本地推論仍需自備硬體。GitHub 的用量與服務條款依帳號及當日官方政策為準。

程式碼採 MIT 授權；第三方來源標題、短摘錄與商標仍屬原權利人。
