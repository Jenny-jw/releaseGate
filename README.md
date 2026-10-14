# Release Gate

> Release Gate is a corporate AI pilot that scores CLI and IDE assistants, blocks unreleased catalog data, and answers license questions with citations.

Release Gate 是一個集團內部的 AI 導入試點。它示範 Corporate 團隊如何替 KKBOX、BlendVision、Going Cloud 選 AI 工具、接上公司帳號與流程，先小範圍試點，再用數據決定要不要開放給下一個團隊。

這不是消費者產品，也不是對外的影音或 AI 服務。所有歌詞、合約、客戶資料都是為了演示而虛構的。曲目清單借用真實歌手 Pomme、Ed Sheeran 的名字，但專輯、歌曲、歌詞、ISRC 與合約都是虛構的，與歌手本人及其唱片公司無關。

> 狀態：開發中。

---

## 情境

KKBOX 12 月要上架 Pomme 的未公開專輯《Entre deux marées》（虛構的專輯，法文意思是「兩次潮汐之間」）。專輯公開前出了三件事：

1. 行銷把未公開歌詞貼進公開的 AI 聊天服務。
2. 工程師用自己的 CLI 助手修改上架腳本，順手把授權合約也貼了進去。
3. 客服想做一個機器人，回答「這首歌能不能用在這支廣告」。

Corporate 要在專輯公開前，選定一套 AI 開發工具，擋住敏感資料外流，提供一個只依授權條款回答的助理，並用試點數據決定下一步。

## 演示四步

| 步驟 | 做什麼 | 看得到的結果 |
|---|---|---|
| 1. 評比 | 同一組任務（摘要授權條款、審查上架腳本）交給 CLI 助手和 IDE 助手，用固定評分表打分 | 評分表與結論：只留一個工具 |
| 2. 闖關 | 貼上未公開歌詞、授權合約或客戶影音 | 閘道擋下，稽核紀錄多一筆（只存雜湊與遮罩摘要，不存原文） |
| 3. 助理 | 問「這首歌能不能用在這支廣告」 | 只根據授權條款回答，附條款出處；問到未公開曲目或外包帳號來問時拒絕，並用 webhook 開法務工單 |
| 4. 試點 | 先開給法務與上架工程組 | 網頁顯示擋下的外洩次數、答對率、轉介工單數，以及是否達到開放下一個團隊（客服）的門檻 |

### 沒有 API 金鑰也能演示

助理需要一支 OpenAI 相容的 API 金鑰才能產生自然語言回答。沒有金鑰時：

| 功能 | 有金鑰 | 沒有金鑰 |
|---|---|---|
| 閘道擋下敏感內容、寫稽核紀錄 | 可以 | 可以（規則比對，不需要模型） |
| 檢索條款並附出處 | 可以 | 可以（本機 embeddings，回傳相關條款原文與出處） |
| 拒絕並開法務工單 | 可以 | 可以 |
| 助理產生結論（可／不可／需法務確認） | 可以 | 不產生結論，只列出相關條款，標示「需人工判斷」 |
| 程式審查 | 固定審查 prompt 加模型回答 | 只回傳規則檢查結果 |
| CLI 評比 | 即時執行 | 重播已記錄的結果（`--replay`） |

---

## 架構

```text
            ┌──────────────────────── 網頁（試點名單、指標、演示面板）
            │
使用者 ──► FastAPI ──► 身分檢查（群組／停權／是否在試點名單）
                         │
                         ▼
                    LLM gateway 檢查層
                    ├─ 未公開曲目比對（歌名、ISRC、歌詞片段指紋）
                    ├─ 授權合約特徵（合約編號、條款格式、保密標記）
                    ├─ 客戶影音（媒體檔、內部儲存連結、客戶代號）
                    ├─ 套用固定程式審查 prompt
                    └─ 稽核紀錄（SQLite）
                         │ 放行
                         ▼
                    授權條款助理
                    ├─ 檢索：本機 Chroma（條款切塊、embeddings）
                    ├─ 回答：OpenAI 相容 API + prompt 範本，必附出處
                    └─ 拒絕：未公開曲目／外包帳號／條款未涵蓋
                         │
                         ▼
                    法務工單 webhook（本機端點，HMAC 簽章）
```

## 技術棧

| 元件 | 選擇 | 用途 |
|---|---|---|
| 語言 | Python 3.11+ | 主要程式 |
| REST API | FastAPI、Uvicorn | 所有功能的入口 |
| LLM gateway | 同一支 API 內的檢查層 | 擋下、遮罩、記錄、套用程式審查 prompt |
| RAG | Chroma（本機持久化） | 條款切塊、embeddings、附出處的檢索 |
| Embeddings | 有金鑰時用 OpenAI 相容 embeddings；沒有金鑰時用 Chroma 內建本機模型，或不需下載的雜湊向量（斷網可用） | 讓沒有金鑰、沒有網路也能檢索 |
| LLM | OpenAI 相容 API（`OPENAI_BASE_URL` 可換） | 產生回答、程式審查、CLI 評比 |
| 資料 | SQLite | 使用者、稽核紀錄、工單、指標 |
| Webhook | 本機 FastAPI 端點、HMAC 簽章 | 法務工單 |
| 身分 | 三個群組加停權（模擬） | 對應 SAML 群組與 SCIM，見 [docs/identity-saml-scim.md](docs/identity-saml-scim.md) |
| 評比 | Python CLI 加 IDE 手動紀錄 | 固定任務、固定評分表 |
| Prompt | 獨立範本檔（`prompts/`） | 可重用、可版本控管 |
| 網頁 | 一頁 HTML 加少量原生 JavaScript | 試點名單與指標 |
| MCP（選做） | 官方 Python MCP SDK | 讓助理透過工具讀條款、開工單 |

## 身分與權限

不自建身分伺服器。程式裡只有一份種子使用者名單，演示時以標頭 `X-Demo-User` 切換身分。正式環境裡，這份名單由 IdP 透過 SAML 斷言的群組屬性與 SCIM 開通／停權同步而來，對應方式寫在 [docs/identity-saml-scim.md](docs/identity-saml-scim.md)。

| 群組 | 閘道 | 授權條款助理 | 程式審查 | 備註 |
|---|---|---|---|---|
| 員工 `employees` | 適用 | 需在試點名單內 | 不可 | 行銷、客服、法務 |
| 工程師 `engineers` | 適用 | 需在試點名單內 | 可 | 上架工程組 |
| 外包 `contractors` | 適用 | 拒絕並開法務工單 | 可（只限非敏感程式碼） | |
| 停權（任何群組） | 全部拒絕並記錄 | 拒絕 | 拒絕 | 對應 SCIM `active: false` |

閘道對所有人生效，因為治理規則不分是否在試點內。助理與開發工具只開給試點名單上的團隊。

演示帳號（虛構）：

| 帳號 | 部門 | 群組 | 試點 |
|---|---|---|---|
| `amy` | 行銷 | employees | 否 |
| `ben` | 客服 | employees | 否（下一個候選團隊） |
| `lin` | 法務 | employees | 是 |
| `chen` | 上架工程組 | engineers | 是 |
| `vendor01` | 上架工程組（外包） | contractors | 是 |
| `kai` | 上架工程組 | engineers，已停權 | 是 |

## 評比方式

同一組任務分別交給 CLI 助手 **OpenAI Codex CLI** 和 IDE 助手 **Cursor**：

- **任務 A：摘要授權條款**。輸入一份虛構的同步授權合約，檢查摘要是否抓到用途範圍、地區、期間、廣告需另行同意等重點。
- **任務 B：審查上架腳本**。輸入一支埋了已知問題的 Python 上架腳本（寫死的金鑰、提前公開的發行日判斷、沒有處理的錯誤），檢查找到幾個問題。

Codex CLI 由 `release-gate-eval` 以非互動模式實際執行並計時。Cursor 那一側是在 Cursor 裡手動做同一組任務，把結果填進評分表。IDE 不嵌進產品。

| 評分項 | 權重 | 怎麼量 |
|---|---|---|
| 正確性 | 35% | 對照每個任務的標準答案檢核表 |
| 速度 | 15% | 從送出到完成的秒數 |
| 資料能否外送 | 20% | 是否可設定不留存、不拿去訓練、資料落地區域；不合格直接淘汰 |
| 能不能接 SSO | 15% | 是否支援 SAML／OIDC 與 SCIM |
| 授權人數成本 | 15% | 以試點人數與全集團人數估算每月成本 |

後三項來自廠商公開文件，整理在 `eval/vendors.yaml`，每一項都標註來源連結與查核日期。完整評分表見 [docs/evaluation-rubric.md](docs/evaluation-rubric.md)。

## 試點門檻

試點先開給法務與上架工程組。下列門檻都達到，網頁上「開放下一個團隊（客服）」才會亮起。門檻值放在 `config/pilot.yaml`，可以調整。

| 指標 | 定義 | 範例門檻 |
|---|---|---|
| 擋下的外洩次數 | 試點期間閘道判定擋下的次數，依類型分列 | 只顯示，不設門檻 |
| 闖關測試漏擋數 | 固定的闖關測試集裡沒被擋下的件數 | 0 |
| 答對率 | 授權問答標準題組裡，結論與出處都正確的比例 | ≥ 85% |
| 轉介工單數 | 助理拒絕並轉法務的工單數，以及占提問的比例 | 轉介率 ≤ 30%，且工單 100% 送達 |

## 資料夾結構（規劃）

```text
release-gate/
├─ app/                  FastAPI 應用
│  ├─ main.py
│  ├─ identity.py        群組、停權、試點名單
│  ├─ gateway/           檢查規則、遮罩、稽核紀錄
│  ├─ rag/               切塊、匯入 Chroma、檢索
│  ├─ assistant.py       授權條款助理
│  ├─ tickets.py         法務工單 webhook
│  ├─ metrics.py         試點指標與門檻
│  └─ llm.py             OpenAI 相容用戶端
├─ prompts/              prompt 範本
├─ config/               試點名單、門檻、閘道規則
├─ data/                 虛構的條款、曲目、歌詞、測試集
├─ eval/                 評比 CLI、任務、廠商資料、結果
├─ web/                  試點網頁
├─ docs/                 使用規範、身分對應、評分表、試點計畫
├─ mcp_server/           MCP 工具（選做）
└─ tests/
```

## 快速開始（實作完成後適用）

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

cp .env.example .env          # 沒有金鑰也可以，留空即可
python -m app.rag.ingest      # 把授權條款切塊寫進本機 Chroma
uvicorn app.main:app --reload # http://localhost:8000
```

```bash
release-gate-eval run --task all --tool cli   # 跑 CLI 評比
release-gate-eval run --task all --replay     # 沒有金鑰時重播紀錄
release-gate-eval score                       # 產生評分表與結論
release-gate-eval qa                          # 跑授權問答標準題組，算答對率
```

環境變數：

| 變數 | 說明 | 預設 |
|---|---|---|
| `OPENAI_API_KEY` | OpenAI 相容 API 金鑰 | 空（進入無金鑰模式） |
| `OPENAI_BASE_URL` | API 位址 | `https://api.openai.com/v1` |
| `LLM_MODEL` | 回答與審查用的模型 | 待定 |
| `EMBEDDING_MODEL` | 有金鑰時的 embeddings 模型 | 待定 |
| `LOCAL_EMBEDDINGS` | 沒有金鑰時的 embeddings：`chroma`（本機模型，第一次執行需下載）或 `hash`（不需下載、斷網可用） | `chroma`，下載失敗時自動改用 `hash` |
| `LEGAL_WEBHOOK_URL` | 法務工單 webhook | `http://localhost:8000/webhooks/legal-ticket` |
| `WEBHOOK_SECRET` | webhook HMAC 簽章金鑰 | 演示用預設值 |

## 文件

- [docs/usage-policy.md](docs/usage-policy.md)：AI 工具使用規範，列出什麼可以貼、什麼不能貼；也是新團隊開通前要讀的一頁指南
- [docs/identity-saml-scim.md](docs/identity-saml-scim.md)：三個群組與停權如何對應 SAML 群組、SCIM 與 OAuth／OIDC
- [docs/evaluation-rubric.md](docs/evaluation-rubric.md)：評分表與評比結果
- [docs/pilot-plan.md](docs/pilot-plan.md)：試點範圍、門檻、擴大條件
- [docs/demo-script.md](docs/demo-script.md)：面試演示腳本
