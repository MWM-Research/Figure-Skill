# Figure QA checklist

## Scientific

- Every quantitative mark is traceable to a source file and documented transformation.
- Source hashes and every plotted CSV/TSV row-column value pass provenance verification.
- Units, conditions, baselines, sample counts, and uncertainty definitions are correct.
- Arrow direction and line style match the intended causal, temporal, material, or data-flow meaning.
- No generated element is presented as experimental evidence.
- Caption and figure make the same claim.

## Visual

- Reading order is obvious and panel labels are consistent.
- Text remains legible at intended column width.
- Color is not the only carrier of meaning; contrast remains adequate in grayscale where required.
- Axes, ticks, legends, strokes, and whitespace are consistent.
- No clipped labels, overlapping elements, accidental placeholders, or unexplained abbreviations remain.

## Delivery

- Editable source opens successfully.
- The approved plan contains every delivered panel and has no unresolved open questions.
- SVG/PDF is vector-based where expected and PNG is a faithful preview.
- Fonts are embedded or safely substituted.
- Prompts, model/provider metadata, plotting scripts, environment details, and provenance are retained.
- Temporary inputs, secrets, and private data are excluded from the delivery package.
