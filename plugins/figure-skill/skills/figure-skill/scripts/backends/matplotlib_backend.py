#!/usr/bin/env python3
"""Compatibility entry point for deterministic Figure Skill data plots."""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from plotting.io import read_records
from plotting.renderer import main, render_grid_panel, render_panel

__all__ = ["read_records", "render_panel", "render_grid_panel", "main"]


if __name__ == "__main__":
    raise SystemExit(main())
