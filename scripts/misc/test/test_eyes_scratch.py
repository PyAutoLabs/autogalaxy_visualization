"""Hermetic tests for ``_viz_cli.mirror_to_scratch`` (the opt-in Eyes scratch mirror).

A fabricated ``scripts/<domain>/images/`` tree in a tmp dir stands in for real
producer output (``repo_root`` is monkeypatched to it), so no figures are rendered and
the real ``scripts/`` tree is never read. The points: unset env var = no-op, the layout
is ``$PYAUTO_EYES_SCRATCH/autogalaxy/<domain>/<subpath below images/>``, a re-mirror leaves
no stale figure, and ``misc`` is never mirrored.

Run::

    cd autogalaxy_visualization
    python -m pytest scripts/misc/test/test_eyes_scratch.py
"""

from __future__ import annotations

import importlib.util
import sys as _sys
from pathlib import Path as _Path

import pytest


def _repo_root() -> _Path:
    for _p in _Path(__file__).resolve().parents:
        if (_p / "ruff.toml").exists():
            return _p
    raise RuntimeError("autogalaxy_visualization root (ruff.toml) not found")


_spec = importlib.util.spec_from_file_location("viz_cli_under_test", _repo_root() / "_viz_cli.py")
viz = importlib.util.module_from_spec(_spec)
_sys.modules[_spec.name] = viz
_spec.loader.exec_module(viz)


@pytest.fixture
def fake_repo(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    for rel in ("alpha/images/visualization/a.png", "alpha/images/visualization/sub/b.png"):
        (root / "scripts" / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / "scripts" / rel).write_bytes(b"png")
    (root / "scripts" / "beta" / "images" / "visualization").mkdir(parents=True)
    (root / "scripts" / "beta" / "images" / "visualization" / "c.png").write_bytes(b"png")
    (root / "scripts" / "misc" / "images").mkdir(parents=True)
    (root / "scripts" / "misc" / "images" / "ignored.png").write_bytes(b"png")
    monkeypatch.setattr(viz, "repo_root", lambda: root)
    return root


def test_unset_env_is_a_no_op(fake_repo, monkeypatch):
    monkeypatch.delenv(viz.EYES_SCRATCH_ENV, raising=False)
    assert viz.mirror_to_scratch() is None


def test_mirror_layout_and_no_stale_figures(fake_repo, tmp_path, monkeypatch):
    scratch = tmp_path / "scratch"
    monkeypatch.setenv(viz.EYES_SCRATCH_ENV, str(scratch))

    lib_dir = viz.mirror_to_scratch()

    assert lib_dir == scratch / "autogalaxy"
    got = sorted(p.relative_to(lib_dir).as_posix() for p in lib_dir.rglob("*.png"))
    assert got == [
        "alpha/visualization/a.png",
        "alpha/visualization/sub/b.png",
        "beta/visualization/c.png",
    ]

    (fake_repo / "scripts" / "alpha" / "images" / "visualization" / "a.png").unlink()
    viz.mirror_to_scratch(["alpha"])
    assert not (lib_dir / "alpha" / "visualization" / "a.png").exists()
    assert (lib_dir / "alpha" / "visualization" / "sub" / "b.png").exists()
    assert (lib_dir / "beta" / "visualization" / "c.png").exists()
