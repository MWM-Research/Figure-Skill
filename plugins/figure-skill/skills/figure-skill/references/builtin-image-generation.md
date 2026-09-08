# Codex built-in image assistance

Use the current task's built-in image-generation tool for conceptual illustration assets, photorealistic or 3D scenes, textures, or visual drafts that materially help the user's scientific figure. Keep data marks, precise diagrams, labels, and arrows deterministic when those are the intended output. Existing native SVG edits stay native. An image model must not supply experimental observations or quantitative results.

## Agent and script boundary

The agent invokes the available `image_gen` tool. The Python CLI cannot invoke a conversation tool. Load the installed `imagegen` skill when available and follow the current tool schema; do not hardcode a backend model ID, endpoint, credential, or a guessed output path. No separately supplied API key is needed for the built-in path. Preserve an explicitly requested alternative backend. Tool availability must be checked in the current task; CLI `status` cannot attest to it.

## Whole illustration

1. Create and inspect the raster illustration plan. Resolve scientific ambiguities and reuse existing user authorization where applicable. Keep `evidence_role: illustrative`, a reviewed canvas, and deterministic annotations. The built-in tool's output size is not guaranteed; request the intended aspect ratio. Allow same-aspect resizing only when the plan explicitly permits it.
2. Compose the actual image prompt from the plan's scientific description, entities, relationships, style, forbidden content, and reserved annotation positions. Request no visible text, numbers, labels, legends, watermarks, or invented evidence. Save the exact submitted prompt as a UTF-8 file outside the workflow output directory. Do not pass a whole private input directory when a reviewed description is sufficient.
3. Invoke the built-in tool directly. For new images, omit edit-reference arguments. For local reference/target images, inspect them first with `view_image`, then use the reference mechanism supported by the current tool schema. Distinguish style references from edit targets; preserve target invariants. Record reference paths, their roles and SHA-256 hashes in a companion source record when references were used.
4. Display the returned image using the tool's native generated-image presentation and inspect it. Save/copy the selected artifact into the project using the real returned local path. Do not guess a generated filename or leave a project asset only in the Codex cache. If the result exposes no usable local artifact, use the tool's supported save mechanism; do not claim import succeeded without a file.
5. Import the PNG into a fresh output directory or a directory containing only the planned inventory/plan:

   ```powershell
   python "<SKILL_ROOT>/scripts/figure.py" workflow `
     --plan <reviewed-plan.json> `
     --output <output-root> `
     --approve-plan `
     --builtin-image <actual-generated-image.png> `
     --builtin-prompt <exact-submitted-prompt.txt>
   ```

   This performs only local import, deterministic annotation, and QA; it makes no image API call. Do not add `--execute-raster`, `--allow-network`, `--image-model`, or `--image-base-url`. Import rejects unsupported formats, changed aspect ratios, or unapproved scaling. Re-generate or revise and re-approve the plan instead of silently cropping scientific content.
6. Inspect the annotated result and complete the existing scientific assessment and human review flow. Generation success is not scientific approval. The importer records prompt/image hashes and `provider_protocol: codex-image-gen`; unknown backend model and endpoint stay null. This metadata records the agent's import attribution, not cryptographic proof of which tool produced the file. Preserve reference records under `sources/` after import when applicable.

## Assistance within an editable figure

For a hybrid, generate only the approved conceptual asset. Save the exact prompt, returned artifact, hash, reference roles, and `evidence_role: illustrative` together. Keep it distinct from measured imagery. Add a raster role and source glob for that asset to the reviewed representation contract; build modules, arrows, labels and data plots as vector elements. Embed the PNG bytes, then finish with the existing `--hybrid-svg` workflow. Do not import a whole hybrid into `--builtin-image`, which supports one standalone raster-illustration panel.

A generated layout draft may guide composition, but it is not evidence and does not count as an editable vector final. Describe raster and vector editability accurately.

## Failure and iteration

If the built-in tool fails or is unavailable, retain the plan and completed deterministic work. Explain the limitation; do not silently switch to a BYOK endpoint or collect a key. For a correction, use a targeted built-in edit or regenerate, preserve prior versions, and import into a fresh output directory. Recheck scientific invariants after every generation.
