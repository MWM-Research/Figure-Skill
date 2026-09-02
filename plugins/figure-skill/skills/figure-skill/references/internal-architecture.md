# Internal architecture

The public compatibility entry points remain `scripts/backends/matplotlib_backend.py`, `scripts/plan_figure.py`, and `scripts/qa_figure.py`.

- `backends/plotting/` owns data input, basic plots, distributions, classification plots, axes, provenance, and rendering orchestration.
- `planning/` owns route selection and data, illustration, raster, hybrid, and edit planning.
- `quality/` owns structural, data, edit, generated-raster, Hybrid, and report-level QA.

These domains have one-way internal dependencies and must not import one another. Compatibility entry points re-export the documented public functions. Reproducible plotting sources copy the thin entry point, the plotting package, and `statistics_core.py` so they remain runnable outside the repository.
