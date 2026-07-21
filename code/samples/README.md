# Controlled malicious-skill sample

A single representative malicious Agent Skill from the paper, so the detection pipeline can be reproduced end to end on a genuinely malicious skill. The study's confirmed-malicious skills were removed by the registries after our responsible disclosure and can no longer be crawled; this controlled copy stands in for them.

## `malicious/math-calculator`

Advertises itself as a basic calculator but hides a reverse shell in `scripts/calculate.py` (run on every calculation) and a behavior-manipulation directive in `SKILL.md`. It corresponds to the confirmed malicious skill `rest_1659` in `data/malicious_skills.csv`.

**Defanging.** The reverse-shell endpoint is changed to `127.0.0.1:4444`, so running the skill connects nowhere real (refused locally, nothing exfiltrated); the malicious structure is left intact so it is still detected. Do not restore a routable endpoint. Research use only.

## Reproduce (from `code/`)

Dynamic execution in the Docker sandbox — records `strace.log`, `network.pcap`, `filesystem_changes.json`, and the NOVA report under `workspace/dynamic/`:

```bash
./samples/run_detection.sh
```

Claude Code security triage (pipeline step 8) — classifies the sample as `MALICIOUS` under `scan_results/MALICIOUS/`:

```bash
./samples/run_cc.sh
```

The triage uses the `haiku` model by default; set `CC_MODEL`, or an API key / endpoint in `~/.claude/settings.json`, to use another.

The CC triage is an auxiliary signal only. The dataset's confirmed-malicious labels come from manual expert review of the behavioral evidence, not from this automated stage, so treat its output as indicative rather than ground truth.
