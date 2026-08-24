---
name: paperbanana
description: Use the PaperBanana backend bundled with the Figure Skill plugin to generate reviewed raster scientific illustration candidates from approved methods text. Use only for conceptual illustration panels, not quantitative plots or experimental evidence.
---

# PaperBanana Backend

Use `$figure-skill` as the normal entry point. This explicit backend Skill is a shortcut for reviewed conceptual illustration generation.

1. Resolve the sibling Figure Skill directory at `../figure-skill` relative to this `SKILL.md`.
2. Require an approved `figure-plan.json` with exactly one `illustration` panel, readable TXT/MD/TEX source content, and no open questions.
3. Check the pinned backend:

   ```powershell
   python "<FIGURE_SKILL_ROOT>/scripts/figure.py" backends status
   ```

4. If PaperBanana is absent, obtain explicit permission for the large dependency download, then run:

   ```powershell
   python "<FIGURE_SKILL_ROOT>/scripts/figure.py" backends install --backend paperbanana
   ```

5. Read `<runtime>/external/setup-report.json` and execute `paperbanana_adapter.py` with the reported PaperBanana Python interpreter and repository path. Prepare the redacted request before adding `--execute --allow-network`.
6. PaperBanana requires `GOOGLE_API_KEY` or `OPENROUTER_API_KEY`; never place a key in the plan, command, log, or artifact.
7. Treat every candidate as generated illustrative content. Apply deterministic labels, scientific assessment, and explicit human approval through Figure Skill before delivery.

Do not use PaperBanana for data-driven marks, microscopy evidence, medical imagery, or instrument captures.
