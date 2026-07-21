# Judge-first, event-driven demo video production pack

Target: about 2:02 and always under three minutes, 16:9, 1080p, English voiceover, large captions, no copyrighted media. The video must show a working product and audibly explain how Codex and GPT-5.6 were used.

## The around-30-second contract

**Around 0:30, the judge has understood three complete ideas:** the repeated friction, why accumulation is not improvement, and how the collaboration loop closes.

The first three caption cues stay on one **split screen**. The left shows only the current Codex session; the right visibly grows from one rule, to a rule plus Skill, to a rule plus Skill plus hook. Each repeated failure adds one retained patch, so the accumulation is an event rather than a static before/after comparison.

| Time | Story beat | Visible event |
|---|---|---|
| 0:00-0:12.3 | `FAIL -> PATCH -> FAIL -> PATCH` | One current session fails on the left while the right-side stack grows from rule, to Skill, to hook |
| 0:12.3-0:19.5 | `CREATION IS NOT IMPROVEMENT` | The growing pile gives way to `REUSE / CREATE / PATCH / REVISIT / RETIRE_CANDIDATE` |
| 0:19.5-0:34.1 | `CLOSE THE COLLABORATION LOOP` | Evidence reaches the Agent, a human gate, and the next session; only after the return path closes does the slime-mold path brighten and unsupported branches fade |

The opening must be readable rather than frantic. The loop diagram remains on screen until its return path lights and the narration says the loop is complete before the slime-mold transition.

Keep the **Agent-first** boundary visible: Codex interprets evidence and authors proposals; the runtime only bounds, validates, seals, and applies the exact artifact a human approved.

## Event density after the hook

After the hook, rhythm comes from **event density**, not equal-length explanation cards. **Narration is the clock:** each shot lasts only for its natural spoken line plus a short transition breath. There are no fixed five-second holds.

| Time | Story beat | Event chain |
|---|---|---|
| 0:34.1-0:50.8 | `REAL EVIDENCE` | `14 rollout files -> 6 sessions` -> remove `8 forks / 210 duplicate user turns` -> `PATCH + NO CHANGE / REUSE` |
| 0:50.8-0:58.8 | `REUSE BEFORE CREATION` | Existing rule resolves the cited evidence -> Codex emits `REUSE EXISTING RULE`, not another instruction |
| 0:58.8-1:30.6 | `CHAIN OF CUSTODY` | Runtime bounds evidence -> GPT-5.6 authors -> runtime validates -> digest seals -> one byte changes -> deterministic rejection -> reviewed bytes return -> human approval -> receipt |
| 1:30.6-1:52.3 | `FUTURE EVIDENCE DECIDES` | Later review restores the success contract -> compare expected effect and withdrawal condition -> reinforce / repair / `RETIRE_CANDIDATE` -> human-controlled archive and rollback |
| 1:52.3-2:02.2 | `WHAT METABOLISM MEANS` | `NOT MODEL TRAINING` appears as an overlay, then the slime-mold motif closes around the final line |

The real numbers come from **one real seven-day review** whose raw logs stayed local. This is **not a benchmark**. The later lifecycle sequence must stay visibly labeled `ISOLATED LIFECYCLE FIXTURE`; it demonstrates implemented mechanics, not measured long-term impact.

## Final line

> **An Agent can add. A healthy collaboration can also let go.**

Keep the responsibility signature on the final frame:

> Agent thinks. Runtime remembers. Human decides.

## Commands represented in the video

Real-session evaluation:

```powershell
python examples/run_real_session_evaluation.py
```

Fresh evidence packet for the active Agent:

```powershell
python examples/run_agent_first_demo.py --prepare-only --output-root .demo-live
```

Reproducible safety path:

```powershell
python examples/run_agent_first_demo.py --output-root .demo-recorded
```

The last command uses a **recorded Codex-authored fixture** so judges can reproduce the lifecycle without authentication. Never present it as a live model call.

## Visual language

- **Bright green path:** a workflow supported by observed use.
- **Amber node:** an intervention awaiting human judgment.
- **Blue boundary:** deterministic evidence, hash, and path gates.
- **Faded branch:** an unsupported intervention that remains recoverable.

The slime mold is procedural, not biological. It does not imply autonomous evolution, weight updates, or causal proof after one successful session.

## Voice, privacy, and claim rules

- Reuse the user-approved Kokoro-82M `af_bella` voice.
- Preserve a natural voice pace. Never time-compress a cue; extend the slide instead.
- Keep every subtitle cue to at most two lines and 38 characters per line.
- Narrate `GPT-5.6` as "G P T five point six."
- Keep the mix near -16 LUFS with peaks below -1 dBFS.
- Show only isolated synthetic data and the committed, manually paraphrased real-session fixture.
- Do not expose raw session text, account names, real paths, notifications, credentials, or private Skills.
- Keep `ONE USER / 7 DAYS / NOT A BENCHMARK` visible with the real numbers.
- Keep `ISOLATED LIFECYCLE FIXTURE` visible throughout the future-review sequence.
- Verify public YouTube visibility, duration under three minutes, 1080p H.264, AAC audio, and readable captions.
