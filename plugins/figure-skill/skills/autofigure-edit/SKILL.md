---
name: autofigure-edit
description: Use the AutoFigure-Edit backend bundled with the Figure Skill plugin for reviewed raster-to-SVG reconstruction or methods-to-SVG generation. Use when a supplied raster draft must become editable SVG and deterministic native reconstruction is insufficient.
---

# AutoFigure-Edit Backend

Use `$figure-skill` as the normal entry point. This explicit backend Skill is a shortcut for the model-assisted SVG route.

1. Resolve the sibling Figure Skill directory at `../figure-skill` relative to this `SKILL.md`.
2. Require an approved edit or illustration plan, an explicit raster/method source, and no open questions.
3. Check the pinned backend:

   ```powershell
   python "<FIGURE_SKILL_ROOT>/scripts/figure.py" backends status
   ```

4. If AutoFigure-Edit is absent, obtain explicit permission for the large dependency download, then run:

   ```powershell
   python "<FIGURE_SKILL_ROOT>/scripts/figure.py" backends install --backend autofigure-edit
   ```

5. Read `<runtime>/external/setup-report.json` and execute `autofigure_edit_adapter.py` with the reported AutoFigure Python interpreter and repository path. Prepare the redacted request first.
6. Prefer the reviewed custom provider configuration and `sam_backend=none` when no paid or local SAM service is authorized. Execute only with `--execute --allow-network`.
7. Reject outputs that embed the source raster as a full-canvas `<image>`, omit vector shapes, change required text, or fail node/edge topology review.

Keep credentials outside plans, commands, logs, and generated artifacts.
