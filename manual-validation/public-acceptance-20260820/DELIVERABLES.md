# Public acceptance deliverables

## Sources

- `sources/SOURCES.md` - source URLs, licenses, attribution
- `sources/download-hashes.json` - SHA-256 hashes
- `inputs/iris.csv` - normalized 150-row Iris table
- `inputs/methods.txt` - attributed scikit-learn pipeline paraphrase
- `scripts/download_sources.ps1` - reproducible public download and hash generation
- `scripts/prepare_iris.py` - deterministic UCI conversion and row/class validation
- `scripts/render_and_compare_reconstructions.py` - pure-SVG checks and comparison metrics
- `scripts/make_contact_sheet.py` - visual QA sheet generation

## Accepted route outputs

- `outputs/data-plot/final/figure.svg|pdf|png`
- `outputs/illustration/final/figure.svg|pdf|png`
- `outputs/illustration/sources/panel_a.drawio`
- `outputs/composite/final/figure.svg|pdf|png`
- `outputs/composite/sources/panel_a.drawio`
- `outputs/edit/final/figure.svg|png`
- `outputs/edit/provenance/edit-provenance.json`

## Raster reconstruction outputs

- `outputs/reconstruction-artificial-neuron-retry-gemini/final.svg`
- `outputs/reconstruction-artificial-neuron-retry-gemini/final-preview.png`
- `outputs/reconstruction-artificial-neuron-retry-gemini/verification-report.json`
- `outputs/reconstruction-neural-network-ground-truth-retry-gemini/final.svg`
- `outputs/reconstruction-neural-network-ground-truth-retry-gemini/final-preview.png`
- `outputs/reconstruction-neural-network-ground-truth-retry-gemini/verification-report.json`

## Reports

- `ACCEPTANCE_REPORT.md` - human-readable acceptance decision
- `reports/acceptance-summary.json` - machine-readable summary
- `reports/visual-qa-contact-sheet.png` - all principal outputs

Failed attempts are retained under their original output directories as negative-test evidence and must not be treated as deliverables.
