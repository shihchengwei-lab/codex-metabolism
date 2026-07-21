# Codex Metabolism

> **大家都在替 Agent 增加記憶；我們替它建立代謝。**

[English](README.md) · OpenAI Build Week 組別：**Developer Tools**

[![CI](https://github.com/shihchengwei-lab/codex-metabolism/actions/workflows/ci.yml/badge.svg)](https://github.com/shihchengwei-lab/codex-metabolism/actions/workflows/ci.yml)

Codex Metabolism 讓人與 AI 共同改善協作層：一起完成的困難或常見工作，可以成為可重用 workflow；後續 session 再暴露 skill 與環境中的摩擦，review 決定該新增、修補、保留或退休什麼。它不更新模型參數，成長的是一人一 Agent 之間可檢查、可撤回的程序性環境。

## 模型協作 review（建議主路徑）

```powershell
codex-metabolism review --days 7 --advisor codex
```

GPT-5.6 負責理解協作機會；deterministic code 限制 evidence、schema、staging 與安全邊界；最後由人決定。除了 feedback 與 interruption，高投入的 tool-use session 也會成為 `workflow_candidate`，供模型判斷是否值得沉澱為 `SKILL`；它只是候選，不會被冒充成已完成任務。最多 24 個 bounded、pseudonymous candidates 只在明確 opt-in 後送到 OpenAI，模型建議不會自動成為 live mutation。

## Deterministic fallback（離線備援）

`codex-metabolism review --days 7 --advisor none` 只在本機報告 coverage、硬訊號、abstention 與 exact-pattern decisions，不做語意理解；它是隱私或未登入環境的 fallback，不是完整產品體驗。

## 一個失敗的前後對照——synthetic replay

**之前：**兩個 session 都讓 `deploy production` 失敗，使用者也兩次修正「先跑 `preflight`」；有用與未使用的 skill 卻同樣永久堆著。

**review 後：**先 staging 機械性 `PreToolUse` guard，保留有證據的 skill，並把 `old-unused` 標成可逆封存候選。人沒有看證據並批准前，不動 live state。

**後續：**兩次可驗證成功得到 `KEEP HARNESS (VALIDATED)`，active receipt 也阻止重複提案。代謝不是只加東西，而是建立、驗證、強化與撤回路徑。

## 評審 60 秒快速入口

需要 Python 3.11 以上；不必安裝 package，不需要 API key、Codex 登入或私人 session。

```bash
git clone https://github.com/shihchengwei-lab/codex-metabolism.git
cd codex-metabolism
python examples/run_closed_loop_demo.py
```

```text
First review: CREATE HARNESS + PATCH RULE
Second review: KEEP HARNESS (VALIDATED)
```

它只操作隔離的 synthetic fixtures，不讀取或修改真實 session、skills、hooks 或 `AGENTS.md`。

![Codex Metabolism 評審 demo：觀察、介入、評估與剪枝](docs/assets/judge-demo.png)

## 證據一覽

| 證據 | 重播方式 | 證明什麼 |
|---|---|---|
| 兩代閉環 | 上方命令 | 提案、隔離批准、後續驗證、阻止重複建立 |
| 跨層摩擦 | `python examples/run_friction_cases_demo.py` | 既有 tool 與 contextual skill，不只 command order |
| 不完美資料 | `python examples/run_messy_evidence_demo.py` | action 一次、abstain 兩次、coverage warning、阻止不安全退休 |
| Detector 邊界 | `python examples/run_detector_evaluation.py` | 27 個 synthetic 案例：precision `1.000`、recall `0.500`、零 false positive |
| 真實 session review | [匿名聚合報告](docs/REAL_SESSION_REVIEW.md) | 213/213 檔案成功解析；看見摩擦；沒有硬造變更 |

[Detector 邊界評估](docs/EVALUATION.md) · [真實 session review](docs/REAL_SESSION_REVIEW.md) · [Devpost 草稿](docs/DEVPOST.md) · [影片製作包](docs/DEMO_VIDEO.md)

不完美資料重播也會產生 `friction-evidence.csv`：一筆 decision、兩筆明確 abstention，以及 deterministic references 與 coverage；不包含原始 prompt、證據摘要、session ID 或本機路徑。一般 review 的 `--export-evidence` 只輸出已產生的 decisions；這個壓力測試另把已計算好的 abstentions 傳給 exporter，exporter 本身不會推論第五種 decision。

## 四層介入與閉環

- `HARNESS`：hooks、測試、scripts、config 等機械層。
- `TOOL`：已安裝能力、plugin、CLI 與 reviewed OSS。
- `SKILL`：需要情境判斷的可重用工作流。
- `RULE`：`AGENTS.md` 的有上限持久規則。

```text
人與 Codex 共同完成工作
    ↓
可重用 workflow 候選 → proposed SKILL
    ↓
新 session 使用並暴露 feedback、interruption、recovery
    ↓
手動 review 或明確啟用的排程觸發
    ↓
GPT-5.6 review → 必要性 → 內建 → 已安裝 → repo → 外部生態
    ↓
CREATE / PATCH / KEEP / RETIRE_CANDIDATE
    ↓
staging → 人類批准 → 新 session 評估
    ↓
VALIDATED / INEFFECTIVE / IDLE_CANDIDATE
    ↓
保留 / 修補 / 回滾 / 封存 ↺
```

parser 失敗不會被說成未使用，沉默不等於品質。Detector 故意保守；產品的新意是包在外面的 evidence → intervention → evaluation 生命週期。

**目前邊界：**真實 session review 已做到觀察、abstention 理由、review guidance 與 staging 建議。完整迴圈已作為 lifecycle mechanics 實作並由 synthetic replay 展示；真實長期驗證仍是未來工作。

## Codex、GPT-5.6 與人的分工

- **Codex + GPT-5.6：**檢查真實 JSONL 變體、區分證據與推論、先找既有工具、以失敗測試推進，完成 receipt、evaluation 與 rollback。
- **人類：**決定機械層優先、建立前爬梯、managed rules 上限、保護 human-owned `AGENTS.md`，且每次 mutation 都要批准。
- **runtime：**公開 deterministic demo 不呼叫模型；選配 advisor 才透過既有 Codex 登入，將最多 24 個 bounded、pseudonymous feedback／interruption candidates 交給 GPT-5.6。模型可挑戰既有 decision，也能在 strict detector abstain 時提出最多八項語意建議；建議不會自動變成 decision，且不能越過 human gate。

## 使用方式

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e .
codex-metabolism review --days 7 --advisor codex --export-evidence friction-evidence.csv
```

review 只寫 `.codex-metabolism/`；同一專案持續使用相同 output directory，讓 `interventions.jsonl` 串接批准與後續證據。`--export-evidence` 是選配，只把已產生的 decisions 輸出為結構化、匿名化的 review 證據。

## 讓迴圈持續運轉——明確啟用

**預設不會安裝任何排程。**明確啟用一次：

```powershell
codex-metabolism enable --every-days 7 --after-sessions 10
codex-metabolism status
codex-metabolism disable
```

Windows 使用 Windows Task Scheduler，macOS 使用 `launchd`，Linux 使用 systemd user timer。排程檔位於 `.codex-metabolism/automation/run-scheduled-review.cmd`、`~/Library/LaunchAgents/`、`~/.config/systemd/user/`；本機狀態是 `config.json`、`heartbeat.json`、`NOTICE.md`。

每天檢查一次；至少要有一個新 session，且累積十個新 session 或經過七天才 review。**若沒有先前 staged review，第一次啟用以前的 session 不算新 session。**背景只能 Observe、Decide、Stage，**不會自動 Apply**、安裝、啟用、封存或刪除；GPT-5.6 advisor 與 `--search-oss` 維持關閉，除非明確同意。

`status` 對 `unregistered`、`error`、`overdue` 回傳非零狀態。完全未啟動的程序無法自報，因此 OS scheduler history 仍是外部檢查。

## `AGENTS.md` 邊界

會評估 user、project 與 nested scope 的整份檔案，但批准後只能改既存合法區域：

```markdown
<!-- codex-metabolism:managed-start -->
- 這裡放有上限的機器管理規則。
<!-- codex-metabolism:managed-end -->
```

marker 外只提建議。Apply 受整份 SHA-256 保護，marker 無效就拒絕，managed block 最多十條且可回滾。正確檔名是 `AGENTS.md`，不是 `AGENT.md`。

## 批准命令

```powershell
codex-metabolism apply <decision-id> --project-root .
codex-metabolism activate-harness <decision-id> --confirmed-trusted
codex-metabolism rollback <original-decision-id> --project-root .
codex-metabolism archive <decision-id>
codex-metabolism restore <original-decision-id>
codex-metabolism activate-tool <decision-id> --artifact <existing-path-or-command>
codex-metabolism retire-tool <decision-id> --confirmed-inactive
codex-metabolism reject <decision-id>
```

外部工具不會被自動下載、安裝、停用或刪除；新 hook 在 Codex `/hooks` 審查前維持 `PENDING_TRUST`。

## 新建前的爬梯

必要性 → Codex 內建 → 已安裝 → repo 既有 → 外部生態。外部層沒查完時，新 `CREATE` 保持 `needs_research`；`--search-oss` 只送 allowlisted keywords，不送 transcript、路徑或憑證。

## 選配 live GPT-5.6 advisor

```powershell
codex-metabolism review --days 7 --advisor codex --advisor-model gpt-5.6-sol
```

它是 read-only、schema-bounded、non-authoritative。已驗證的 synthetic run 用時 48.5 秒：同意 `CREATE HARNESS`，但用 `KEEP RULE` 挑戰 deterministic `PATCH RULE`；它不能越過 deterministic gates。

## 證據與安全底線

- recurring friction 需要兩個 corrected same-command recovery；普通 retry abstain。
- demonstration guard 只放行 exact reviewed `required && protected`。
- coverage failure 保持 unknown；review 永遠 stage-only。
- mutation 受 decision ID 與 hash 保護；retirement 要人批准且只封存。
- [Detector 邊界評估](docs/EVALUATION.md) 是 synthetic capability test，不是真實使用者 impact。

## 開發、CI 與支援平台

```powershell
python -m unittest discover -s tests -v
python examples/run_detector_evaluation.py
python -m build
```

- **Windows, Python 3.12：**本 checkout 與 clean public clone 已驗證。
- **Linux, Python 3.12：**獨立 clean clone 驗證 demo 與完整 tests。
- **macOS, Python 3.11+：**依 stdlib portability 設計，尚未實機驗證。

CI 覆蓋 Python 3.11/3.12 × Ubuntu/Windows。MIT License；外部專案保留各自授權，repo 不 vendor 其程式碼。
