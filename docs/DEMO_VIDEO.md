# Agent-first demo video production pack

This plan replaces the v0.1 detector/advisor story with the current **Agent-first** architecture. Target: 2:20–2:40, 16:9, 1080p, English voiceover, large captions, no copyrighted media.

## One story only

Two sessions repeat the same deployment mistake using different words and commands while the collaboration environment keeps accumulating. The runtime preserves neutral evidence. The active Codex Agent recognizes one underlying workflow, checks existing capabilities, and authors a complete skill. The runtime seals exact bytes and generates an approval digest; the human approves that version; the next review sees the original evaluation contract and receipt history; rollback archives the skill.

Do not show a deterministic detector making the recommendation. Do not introduce a second model as an advisor. **The Codex session on screen is the AI.**

## Shot list

| Time | Shot | Judge takeaway |
|---|---|---|
| 0:00–0:13 | Split screen: the same user correction returns in two sessions; stale rules and skills pile up beside it | Repetition plus accumulation is the pain |
| 0:13–0:29 | Slime-mold path opens, one useful route brightens, unused branches slowly fade | Metabolism means reinforcement and subtraction, not memory alone |
| 0:29–0:43 | Three large cards: `CODEX — understand + author`, `RUNTIME — remember + constrain`, `HUMAN — approve + reverse` | The responsibility boundary is instantly clear |
| 0:43–0:55 | Run `python examples/run_agent_first_demo.py --prepare-only --output-root <isolated-dir>` | Runtime produces evidence and explicitly reports zero semantic decisions |
| 0:55–1:18 | In Codex, paste the printed `$codex-metabolism` prompt; show it grouping the differently worded sessions | GPT-5.6 performs the semantic work in the actual Agent surface |
| 1:18–1:36 | Codex checks built-in → installed → repository → ecosystem, reuses the repository preflight, and writes the full `deploy-safely` skill | Existing before new; artifact is useful, not a generic template |
| 1:36–1:52 | Show evidence IDs, uncertainty, expected effect, rollback condition, exact diff, and approval digest | Approval is bound to that version |
| 1:52–2:05 | Stage succeeds; deliberately alter a staged byte in a quick inset and show the gate reject it; restore the reviewed bytes | Deterministic code is a firewall, not the brain |
| 2:05–2:19 | Human approves the displayed digest in the isolated demo; show `ACTIVE` receipt with its evaluation contract, then approved rollback moving the skill into archive | Exact-version control and Skill reversibility are real |
| 2:19–2:34 | Return to the bright slime-mold path and faded branches; overlay `SILENCE IS NOT SUCCESS` | Future evidence drives keep, repair, or withdrawal; no magic-effect claim |
| 2:34–2:40 | Name, repository, `MIT`, `Agent thinks. Runtime remembers and constrains.` | Memorable close |

Keep subtitles to one or two short lines. Use hard cuts and one claim per shot; never scroll a long report during narration.

## Commands to capture

Prepare a fresh isolated evidence packet:

```powershell
python examples/run_agent_first_demo.py --prepare-only --output-root .demo-live
```

The command prints a ready-to-paste prompt for the active Codex session. After the live segment, reproduce the complete safety path separately:

```powershell
python examples/run_agent_first_demo.py --output-root .demo-recorded
```

Label the second run **recorded Codex-authored fixture**. It exists so judges can reproduce the lifecycle without authentication; it must not be presented as a live model call.

## Visual language

- **Bright green path:** a workflow that earned attention through observed use.
- **Amber node:** a proposed intervention awaiting human judgment.
- **Blue boundary:** deterministic evidence, hash, and path gates.
- **Faded branch:** an archived or unsupported intervention, still recoverable.

The slime mold is procedural, not biological. It does not imply autonomous evolution, weight updates, or causal proof after one successful session.

## Trust and privacy checklist

- Capture only isolated synthetic sessions and artifacts.
- Keep the active Codex window inside the isolated demo directory.
- Do not show account names, real paths, notifications, credentials, or private skills.
- Show `Runtime interpretation: 0 semantic decisions` long enough to read.
- Show the exact artifact and generated digest before approval.
- Say that bounded redaction is not guaranteed anonymization.
- Say that the current demo proves mechanics and responsibility boundaries, not real-world impact.
- Verify public YouTube visibility, duration under three minutes, 1080p H.264, AAC audio, and readable captions.

## Suggested metadata

**Title:** Codex Metabolism — Agent-first improvement for Codex collaboration

**Description:**

> Codex Metabolism lets the active Codex Agent review recent collaboration, capture reusable work, repair recurring friction, and prune stale interventions. Codex interprets and authors; a zero-dependency runtime preserves lifecycle evidence and binds Skill mutation to an exact, human-reviewed digest. Other layers reuse Git and platform mechanisms. MIT licensed: https://github.com/shihchengwei-lab/codex-metabolism
