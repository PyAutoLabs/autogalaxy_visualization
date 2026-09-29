"""Hermetic tests for ``gallery/gallery_build.py``.

A fabricated ``scripts/alpha/images/visualization/{a.png, sub/b.png}`` tree in a tmp
dir stands in for real producer output. No PyAutoGalaxy import (the version header is
passed explicitly and ``stack_versions`` is stubbed), no real figures: the point is
the tracked ``gallery/viz_manifest.yaml`` shape, the relative links in GALLERY.md, and
that ``--check`` catches a figure set or figure content that drifted from the
committed GALLERY.md / manifest.

The module is loaded straight off its path (``gallery/`` is not a package).

Run::

    cd autogalaxy_visualization
    python -m pytest scripts/misc/test/test_gallery_build.py
"""

from __future__ import annotations

import hashlib
import importlib.util
import sys as _sys
from pathlib import Path as _Path

import pytest
import yaml


def _repo_root() -> _Path:
    for _p in _Path(__file__).resolve().parents:
        if (_p / "ruff.toml").exists():
            return _p
    raise RuntimeError("autogalaxy_visualization root (ruff.toml) not found")


ROOT = _repo_root()
_MODULE_PATH = ROOT / "gallery" / "gallery_build.py"
_spec = importlib.util.spec_from_file_location("gallery_build_under_test", _MODULE_PATH)
gb = importlib.util.module_from_spec(_spec)
_sys.modules[_spec.name] = gb
_spec.loader.exec_module(gb)

PNG_BYTES = b"\x89PNG\r\n\x1a\n"  # a header is enough: the builder never decodes


@pytest.fixture
def tree(tmp_path):
    img = tmp_path / "scripts" / "alpha" / "images" / "visualization"
    (img / "sub").mkdir(parents=True)
    (img / "a.png").write_bytes(PNG_BYTES)
    (img / "sub" / "b.png").write_bytes(PNG_BYTES)
    return tmp_path


def _build(root, *extra):
    return gb.main(["--root", str(root), "--version-string", "9.9.9", *extra])


FAKE_STACK = {"autogalaxy": "9.9.9", "autoarray": "1.0", "autofit": "1.0"}


@pytest.fixture(autouse=True)
def _no_stack_import(monkeypatch):
    """Keep the tests hermetic: never import the PyAuto stack for ``rendered_with``."""
    monkeypatch.setattr(
        gb,
        "stack_versions",
        lambda override=None: {**FAKE_STACK, "autogalaxy": override or "9.9.9"},
    )


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_tracked_manifest_content(tree):
    assert _build(tree) == 0
    doc = yaml.safe_load((tree / "gallery" / "viz_manifest.yaml").read_text())
    assert doc["schema"] == 1
    assert doc["rendered_with"] == FAKE_STACK
    assert doc["generated"]
    assert doc["figure_count"] == 2
    assert doc["figures"] == [
        {
            "file": "scripts/alpha/images/visualization/a.png",
            "producer": "scripts/alpha/visualization.py",
            "domain": "alpha",
            "source": "",
            "bytes": len(PNG_BYTES),
            "sha256": _sha(PNG_BYTES),
        },
        {
            "file": "scripts/alpha/images/visualization/sub/b.png",
            "producer": "scripts/alpha/visualization.py",
            "domain": "alpha",
            "source": "sub",
            "bytes": len(PNG_BYTES),
            "sha256": _sha(PNG_BYTES),
        },
    ]
    # The gitignored copy the Eyes conductor looks for is byte-identical.
    assert (tree / "output" / "gallery" / "viz_manifest.yaml").read_text() == (
        tree / "gallery" / "viz_manifest.yaml"
    ).read_text()
    assert (tree / "output" / "gallery" / "gallery.html").is_file()


def test_manifest_lists_png_figures_only(tree):
    (tree / "scripts" / "alpha" / "images" / "visualization" / "data.fits").write_bytes(b"x")
    assert _build(tree) == 0
    doc = yaml.safe_load((tree / "gallery" / "viz_manifest.yaml").read_text())
    assert [f["file"].rsplit(".", 1)[-1] for f in doc["figures"]] == ["png", "png"]


def test_rebuild_of_unchanged_tree_is_byte_identical(tree):
    assert _build(tree) == 0
    path = tree / "gallery" / "viz_manifest.yaml"
    doc = yaml.safe_load(path.read_text())
    doc["generated"] = "2000-01-01"
    path.write_text(gb.dump_manifest(doc))
    before = path.read_text()
    assert _build(tree) == 0
    # Same figures + same stack: the old date is carried over, nothing to commit.
    assert path.read_text() == before


def test_new_stack_version_restamps_manifest(tree):
    assert _build(tree) == 0
    path = tree / "gallery" / "viz_manifest.yaml"
    doc = yaml.safe_load(path.read_text())
    doc["generated"] = "2000-01-01"
    path.write_text(gb.dump_manifest(doc))
    assert gb.main(["--root", str(tree), "--version-string", "10.0.0"]) == 0
    doc = yaml.safe_load(path.read_text())
    assert doc["rendered_with"]["autogalaxy"] == "10.0.0"
    assert doc["generated"] != "2000-01-01"


def test_check_fails_on_changed_png_bytes(tree):
    assert _build(tree) == 0
    # Same figure set (GALLERY.md still current), different content: stale manifest.
    (tree / "scripts" / "alpha" / "images" / "visualization" / "a.png").write_bytes(
        PNG_BYTES + b"changed"
    )
    assert _build(tree, "--check") == 1
    assert _build(tree) == 0
    assert _build(tree, "--check") == 0


def test_check_fails_without_tracked_manifest(tree):
    assert _build(tree) == 0
    (tree / "gallery" / "viz_manifest.yaml").unlink()
    assert _build(tree, "--check") == 1


def test_check_never_rewrites_tracked_manifest(tree):
    assert _build(tree) == 0
    path = tree / "gallery" / "viz_manifest.yaml"
    before = path.read_text()
    (tree / "scripts" / "alpha" / "images" / "visualization" / "c.png").write_bytes(PNG_BYTES)
    _build(tree, "--check")
    assert path.read_text() == before


def test_gallery_md_links_and_header(tree):
    assert _build(tree) == 0
    md = (tree / "GALLERY.md").read_text()
    assert "![a](scripts/alpha/images/visualization/a.png)" in md
    assert "![b](scripts/alpha/images/visualization/sub/b.png)" in md
    assert "Rendered with PyAutoGalaxy `9.9.9` · 2 figures." in md
    assert "## alpha" in md
    assert "### alpha / visualization" in md
    assert "#### alpha / visualization / sub/" in md
    assert "- [alpha](#alpha)" in md


def test_check_passes_after_build_and_ignores_version(tree):
    assert _build(tree) == 0
    assert _build(tree, "--check") == 0
    # A different version stamp alone is not staleness.
    assert gb.main(["--root", str(tree), "--version-string", "0.0.1", "--check"]) == 0


def test_check_fails_after_extra_png(tree):
    assert _build(tree) == 0
    (tree / "scripts" / "alpha" / "images" / "visualization" / "c.png").write_bytes(PNG_BYTES)
    assert _build(tree, "--check") == 1
    # Rebuilding brings GALLERY.md back in line.
    assert _build(tree) == 0
    assert _build(tree, "--check") == 0


def test_check_fails_without_gallery_md(tree):
    assert _build(tree, "--check") == 1


def test_check_never_rewrites_gallery_md(tree):
    assert _build(tree) == 0
    before = (tree / "GALLERY.md").read_text()
    (tree / "scripts" / "alpha" / "images" / "visualization" / "c.png").write_bytes(PNG_BYTES)
    _build(tree, "--check")
    assert (tree / "GALLERY.md").read_text() == before
