# Detector boundary evaluation

Codex Metabolism intentionally uses a conservative detector before its broader intervention lifecycle. This page measures that detector's public capability boundary instead of implying general session understanding.

## Reproduce it

Requirements: Python 3.11 or newer; no package installation, API key, or private session data.

```bash
python examples/run_detector_evaluation.py
```

Expected summary:

```text
Detector boundary: 24 cases
Precision: 1.000
Recall: 0.500
False positives: 0
Abstentions: 16
```

The retained `detector-evaluation.json` contains every label, observed result, category, and limitation.

## Result

| Measure | Result |
|---|---:|
| Author-defined cases | 24 |
| Labeled recurring-friction positives | 16 |
| Labeled negatives | 8 |
| True positives | 8 |
| False positives | 0 |
| False negatives | 8 |
| True negatives | 8 |
| Precision | 1.000 |
| Recall | 0.500 |
| Abstention rate | 0.667 |

This is a deterministic **synthetic** boundary evaluation, **not a real-world quality benchmark**, user study, or claim that an intervention caused later improvement. Labels are author-defined expectations fixed before detector execution.

## What the detector currently requires

One evidence pattern must appear in **two different sessions**. Each session must contain:

```text
failure → correction → same-command success
```

The command comparison lowercases text and normalizes repeated whitespace. It does not perform semantic clustering. Requiring an intervening correction prevents a normal retry from becoming an invented collaboration problem.

## Case groups

Eight supported positives are detected: exact repeated commands, case and whitespace normalization, differing recognized correction wording, Traditional Chinese correction markers, exact arguments, exact paths, durable rule language, and explicit skill redirection.

Eight deliberately labeled positives remain known misses:

- path variation;
- argument variation;
- command aliases;
- quoted versus unquoted paths;
- unmarked corrections such as a bare “Use …” imperative;
- an equivalent but differently spelled recovery command;
- flag-order variation;
- shell invocation variation.

Eight negatives correctly abstain: normal retry, only one corrected session, correction before failure, correction after success, a single session, cross-session failure/success, failures without recovery, and an unrelated successful command.

## Guard adversarial check

The generated demonstration guard is deliberately narrower than a shell policy engine. It allows only the exact reviewed `required && protected` sequence after case and whitespace normalization. Unit tests reject `echo` spoofing, `||`, quoted required text, command substitution, `;`, reversed order, and repeated protected commands. This closes the known false allow without adding a partial multi-shell parser; unrelated commands remain untouched.

## Interpretation

The current evidence supports a narrow claim: within its declared pattern, the detector abstains rather than generalizing and produced zero false-positive decisions in this suite. The 0.500 recall makes the missing semantic and parameter normalization visible. The product contribution is the evidence-to-intervention-to-later-evaluation lifecycle around this gate, not a claim that the gate already understands arbitrary collaboration behavior.
