# Codex Metabolism

Codex Metabolism 是 Codex 的「AI 協作代謝層」：從近期 session 找出反覆摩擦，先找既有解法，再建立或採用最小介入；之後用新的 session 評估它，最後保留、修補、回滾或剪枝。

[English](README.md) · OpenAI Build Week 組別：**Developer Tools**

## 一個失敗的前後對照

**之前：**兩個 session 都重複執行失敗的 `deploy production`，使用者也重複糾正「先跑 `preflight`」。同時，有用的 skill 與長期未使用的 `old-unused` 都永久堆在工具箱裡。

**review 後：**先 staging 一個能在機械層阻止錯誤順序的 `PreToolUse` guard；保留有使用證據的 skill，把 `old-unused` 標成可封存候選，但絕不自動刪除。人沒有查看證據並批准單一 decision 前，不動 live state。

**後續 session：**兩次可驗證成功讓 guard 得到 `KEEP HARNESS (VALIDATED)`，而 active receipt 會阻止系統重複提議同一個修正。這裡的代謝不是增加更多記憶，而是建立、評估與剪枝協作結構。

## 評審 60 秒快速入口

需要 Python 3.11 以上。不必安裝 package，不需要 API key、Codex 登入或任何私人 session。

```bash
git clone https://github.com/shihchengwei-lab/codex-metabolism.git
cd codex-metabolism
python examples/run_closed_loop_demo.py
```

兩代閉環成功時會看到：

```text
First review: CREATE HARNESS + PATCH RULE
Second review: KEEP HARNESS (VALIDATED)
```

這個命令只把 synthetic fixtures 複製到隔離的暫存目錄，不讀取或修改真實 Codex session、skills、hooks 或 `AGENTS.md`。

![Codex Metabolism 評審 demo：零安裝命令完成觀察、採用、評估與剪枝閉環](docs/assets/judge-demo.png)

## Codex、GPT-5.6 與人的分工

- **Codex + GPT-5.6：**檢查真實 JSONL 變體、區分證據與推論、先找外部既有工具、為每個 implementation slice 先寫失敗測試，並完成回執、後續評估與回滾閉環。
- **人類決策：**把代謝範圍從 skill 擴到機械層與工具、機械解優先、建立前先爬梯、managed rules 有上限、保留 human-owned `AGENTS.md`，且所有 mutation 都要明確批准。
- **runtime 邊界：**公開 deterministic demo 不呼叫模型；選配的 `--advisor codex` 才會透過既有 Codex 登入取得 GPT-5.6 第二意見，已驗證的預設型號是 `gpt-5.6-sol`，而且不能越過 deterministic safety gates。

主要開發 thread 的 `/feedback` Session ID 會直接填入 Devpost，不公開在 repo。英文影片腳本、字幕與隱私安全拍攝清單見 [`docs/DEMO_VIDEO.md`](docs/DEMO_VIDEO.md)。

它不更新模型參數，而是維護 Codex 周圍四層程序性環境：

- `HARNESS`：hooks、測試、scripts、config、權限等機械層。
- `TOOL`：已安裝能力、plugin、CLI 與外部開源工具。
- `SKILL`：需要情境判斷的可重用工作流。
- `RULE`：`AGENTS.md` 的持久協作規則。

## 閉環

```text
協作 session
    ↓
手動 review 或明確啟用的排程觸發
    ↓
review session、coverage、現有介入與工具組合
    ↓
必要性 → Codex 內建 → 已安裝 → repo 既有 → 外部生態
    ↓
CREATE / PATCH / KEEP / RETIRE_CANDIDATE
    ↓
staging + 人類批准
    ↓
新 session 評估
    ↓
VALIDATED / INEFFECTIVE / IDLE_CANDIDATE
    ↓
保留 / 修補 / 回滾 / 封存
    ↺
```

已啟用的介入會抑制重複新建。後續兩個相符成功 session 可支持 `KEEP`；兩個相符失敗 session 會提出 `PATCH`；至少 28 天、十個後續 session 都沒有相符使用機會時，也只會提出低信心退休候選，不把沉默假裝成品質證據。

## 直接跑公開 demo

需要 Python 3.11 以上；核心沒有第三方 runtime dependency。

```powershell
python -m codex_metabolism review --days 7 `
  --codex-home examples/demo-home/.codex `
  --skill-root examples/demo-home/.agents/skills `
  --project-root examples/demo-project `
  --catalog-file examples/reviewed-catalog.json `
  --skillreaper-report examples/skillreaper-report.json `
  --output-dir .demo-review `
  --now 2026-07-20T12:00:00+00:00
```

預期結果：

```text
Staged 4 decisions (4 ready, 0 needs research) at .demo-review
```

四個結果分別是：

- `CREATE HARNESS`：重複部署摩擦改用 `PreToolUse` guard，不再只加文字規則。
- `PATCH RULE`：完整評估 demo 的 `AGENTS.md`，只 stage managed block 的 diff，human-owned 內容不變。
- `KEEP SKILL`：SkillReaper 有 `healthy-skill` 的正向使用證據。
- `RETIRE_CANDIDATE SKILL`：完整生命週期證據支持將 `old-unused` 列為退休候選；review 不搬移、不刪除任何檔案。

若要直接重播兩代閉環，執行：

```powershell
python examples/run_closed_loop_demo.py
```

它會在隔離且保留的暫存目錄中完成第一次 review、批准複製專案裡的 harness 與 managed-block patch、記錄明確的 hook trust 確認步驟、加入兩個後續成功 session，再跑第二次 review。最後必須顯示 `Second review: KEEP HARNESS (VALIDATED)`。這是 synthetic replay，不會修改真實 Codex hook trust store。

## `AGENTS.md` 邊界

Codex Metabolism 會完整評估 user、project 與 nested scope 的 `AGENTS.md`，但只有下列既存標記區域可以在批准後直接改寫：

```markdown
<!-- codex-metabolism:managed-start -->
- 這裡放有上限的機器管理規則。
<!-- codex-metabolism:managed-end -->
```

規則如下：

- review 階段永遠不改 live file。
- `apply` 只能替換一組合法 marker 中間的位元組。
- marker 外完整評估，但只提出建議。
- 整份檔案 SHA-256 與 review 時不一致就拒絕 apply。
- marker 缺失、重複、順序錯誤或不在獨立行時，不可直接寫入。
- managed block 最多十條規則；每次新規則建議最多三項。
- 沒有 marker 時，只建議使用者手動加入，不自行插入。
- managed block 可回滾；human-owned 區域不會被回滾流程觸碰。

實際 Codex 檔名是 `AGENTS.md`，不是 `AGENT.md`。

## 使用方式

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e .
codex-metabolism review --days 7 --search-oss
```

review 只寫入 `.codex-metabolism/`。同一個專案請持續使用同一個 output directory，因為 `interventions.jsonl` 是把批准變更與後續 session 串起來的回執帳本。

## 讓迴圈持續運轉——明確啟用

如果還要使用者記得定期執行 review，操作上的閉環就沒有完成。**預設不會安裝任何排程。**使用者明確啟用一次後，Codex Metabolism 才會安裝 user-level 本機排程：

```powershell
codex-metabolism enable --every-days 7 --after-sessions 10
codex-metabolism status
codex-metabolism disable
```

| 平台 | 原生排程 | 安裝的排程檔案 |
|---|---|---|
| Windows | Windows Task Scheduler | `.codex-metabolism/automation/run-scheduled-review.cmd` |
| macOS | `launchd` agent | `~/Library/LaunchAgents/<schedule-id>.plist` |
| Linux | systemd user timer | `~/.config/systemd/user/<schedule-id>.service` 與 `.timer` |

排程每天檢查一次；只有至少出現一個新 session，並且累積十個新 session 或距離上次成功 review 已七天時，才真正執行分析。沒有新 session 時只更新 idle heartbeat，不空跑 review。若已有 staged review，第一次排程會以它作為時間基準；否則以第一次啟用時間為基準。**若沒有先前 staged review，第一次啟用以前的 session 不算新 session。**

背景流程只能自動完成 Observe、Decide 與 Stage，**不會自動 Apply**、啟用 hook、安裝工具、修改 live `AGENTS.md`、封存 skill 或刪除任何內容。背景使用 deterministic router，不會啟用 GPT-5.6 advisor；`--search-oss` 維持關閉，除非使用者在 `enable` 時明確同意。

專案內可以直接檢查這些狀態：

```text
automation/
├── config.json       # 門檻與完整 staged-review 命令
├── heartbeat.json    # 最後檢查、成功、backlog 與錯誤
└── NOTICE.md         # review 執行後的最新 staged-review 通知
```

原生排程檔位於上表的各平台路徑。`launchd` 的 stdout 與 stderr log 寫入 automation directory；systemd 的執行歷史留在 user journal，Windows 的執行歷史留在 Task Scheduler。

`codex-metabolism status` 會確認原生排程是否仍存在；排程遺失、review 失敗或超過 48 小時沒有 heartbeat 時，分別顯示 `unregistered`、`error` 或 `overdue`，並回傳非零狀態。手動 review 成功時也會更新同一份 heartbeat，避免背景排程立刻重做。

`disable` 只移除原生排程，保留設定與 heartbeat 作為稽核紀錄。作業系統通知是 best effort，可用 `--no-notify` 關閉。完全沒有啟動的程序無法自行回報失敗，因此 `status` 與作業系統排程歷史仍是外部健康檢查。

批准命令：

```powershell
# 套用 staged harness、skill 或合法 managed-block patch
codex-metabolism apply <decision-id> --project-root .

# 新 project hook 先維持 PENDING_TRUST；到 Codex `/hooks` 審查並 trust 後再啟用評估
codex-metabolism activate-harness <decision-id> --confirmed-trusted

# 回滾 active harness、skill patch 或 managed-block patch
codex-metabolism rollback <original-decision-id> --project-root .

# 可逆封存與復原 skill
codex-metabolism archive <decision-id>
codex-metabolism restore <original-decision-id>

# 外部工具由人先審查、安裝，再登記開始評估
codex-metabolism activate-tool <decision-id> --artifact <既存路徑或命令>

# 人先停用或移除外部工具，再登記退休
codex-metabolism retire-tool <retirement-decision-id> --confirmed-inactive

codex-metabolism reject <decision-id>
```

Codex Metabolism 不會自動下載、執行、安裝、停用或刪除外部工具。它只提出採用／退休建議，並記錄人已完成的動作。

同樣地，`apply` 寫入 project hook 後不會冒充它已生效；回執先是 `PENDING_TRUST`。使用者在 Codex `/hooks` 審查並信任後，才用 `activate-harness` 改為 `ACTIVE`。

## 新建前的爬梯

每個新建候選都必須依序檢查：

1. 真的需要嗎？是否至少兩個 session 重複，且有可驗證恢復路徑？
2. Codex 內建能力能否解決？
3. 已安裝的 tool、plugin、skill 或 dependency 能否重用？
4. repo 裡既有 hook、test、script、config 或 harness 能否擴充？
5. 外部開源生態是否已有可審查採用的工具？

外部生態尚未查完時，`CREATE` 只能是 `needs_research`，不能 apply。`--search-oss` 只把白名單化關鍵字送到 GitHub 公開搜尋，不送 session 原文、prompt、本機路徑、憑證或任意參數。

## 選配 live GPT-5.6 advisor

```powershell
codex-metabolism review --days 7 --advisor codex --advisor-model gpt-5.6-sol
```

2026 年 7 月 20 日，我們用同一組公開 synthetic fixtures 實跑 Codex CLI 0.144.5 與 `gpt-5.6-sol`，48.5 秒後取得四項通過 schema 與本地 safety gates 的建議。它同意用 `CREATE HARNESS` 機械性阻止部署順序錯誤，也針對 deterministic `PATCH RULE` 提出 `KEEP RULE`：現有 evidence 證明完整 review，卻沒有證明規則本身有缺陷。這個分歧會被保留為 non-authoritative metadata，不會偷改正式 decision。

## 證據與安全底線

- JSONL 逐行解析，只保留有限 excerpt。
- coverage 是產品輸出；解析不到代表未知，不代表沒使用。
- exit status 與測試結果是硬訊號；使用者修正與推測成功是弱訊號。
- 目前 skill invocation 仍標記為 heuristic，不冒充穩定事件。
- 所有 live mutation 都要求明確 decision ID。
- skill 與 `AGENTS.md` patch 都有 hash gate。
- skill 退休只搬到 archive，不刪除。
- 選配 `--advisor codex` 只提供 GPT-5.6 第二意見，不能越過機械層優先與 adoption ladder。

## 支援平台

- **Windows、Python 3.12：**已在目前 checkout 與公開 repo 的乾淨 clone 驗證。
- **Linux、Python 3.12：**由獨立 reviewer 從乾淨 clone 驗證；closed-loop demo 與完整測試套件皆通過。
- **macOS、Python 3.11+：**依 standard-library-only 設計，尚未實機驗證。

完整技術說明、限制、外部工具分工與測試範圍請見 [README.md](README.md)。
