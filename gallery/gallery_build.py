"""
Gallery: Visualization Contact Sheet, Manifest and GALLERY.md
=============================================================

Builds the three views of every figure the ``scripts/<domain>/visualization*.py``
producers have written under ``scripts/<domain>/images/<script>/**``:

    GALLERY.md                        — TRACKED, GitHub-navigable markdown gallery
                                        (relative image links; domain -> script ->
                                        group -> figure; table of contents; header
                                        with the PyAutoGalaxy version + figure count)
    gallery/viz_manifest.yaml         — TRACKED figure manifest: the read contract
                                        of the PyAutoEyes dashboard (see below)
    output/gallery/gallery.html       — contact sheet (gitignored), Eyes-agent contract
    output/gallery/viz_manifest.yaml  — gitignored copy of the tracked manifest, where
                                        the Brain's Eyes conductor looks for it

The tracked manifest lists every committed PNG figure with its producer script,
domain, source type (the per-source sub-folder, e.g. ``parametric`` / ``delaunay``;
"" for the top-level figures), repo-relative path, byte size and sha256 content hash
(no mtimes, so it is reproducible from a checkout), plus the stack it was rendered
with (``rendered_with:`` — autogalaxy / autoarray / autofit versions) and
the date it last changed (``generated:``). The organ PyAutoEyes reads it to link to
this repo's PNGs; it copies nothing. ``generated:`` and ``rendered_with:`` are carried
over unchanged when a rebuild finds the same figures rendered with the same stack, so
rebuilding an unchanged tree is a no-op for git.

Copied from ``autolens_visualization/gallery/gallery_build.py`` (itself adapted from
``autolens_workspace_test/gallery/gallery_build.py``) with the PyAutoGalaxy stack,
header and titles.

Usage (from the repo root):

    python gallery/gallery_build.py           # build everything
    python gallery/gallery_build.py --check   # rebuild output/gallery/, then FAIL if
                                              # the committed GALLERY.md or
                                              # gallery/viz_manifest.yaml differs from
                                              # what would be regenerated (figure set,
                                              # sizes or content hashes)
    python gallery/gallery_build.py --embed   # also write a self-contained
                                              # output/gallery/gallery_embedded.html

``--check`` never rewrites GALLERY.md or the tracked manifest. For GALLERY.md it
compares everything except the version header line (``Rendered with PyAutoGalaxy ...``);
for the manifest everything except ``generated:`` and ``rendered_with:``. So a PR built
against library mains is not failed by the version string the released-stack render
workflow stamped, while the figure set, grouping, links, sizes and content hashes must
match exactly.
"""

from __future__ import annotations

import argparse
import base64
import datetime
import hashlib
import html
import re
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]

GALLERY_MD = "GALLERY.md"
VERSION_LINE_PREFIX = "Rendered with PyAutoGalaxy"

# The tracked figure manifest (PyAutoEyes' read contract) and its gitignored copy.
TRACKED_MANIFEST = Path("gallery") / "viz_manifest.yaml"
OUTPUT_MANIFEST = Path("output") / "gallery" / "viz_manifest.yaml"
MANIFEST_SCHEMA = 1
STACK = ("autogalaxy", "autoarray", "autofit")
# Header fields a --check ignores (they change with the stack, not the figures).
VOLATILE_KEYS = ("generated", "rendered_with")

CSS = """
body { font-family: sans-serif; margin: 1.5rem; background: #111; color: #ddd; }
h1 { font-size: 1.4rem; } h2 { font-size: 1.2rem; border-bottom: 1px solid #444; padding-bottom: 0.2rem; margin-top: 2rem; }
h3 { font-size: 1.0rem; color: #aaa; margin-top: 1.2rem; }
.grid { display: flex; flex-wrap: wrap; gap: 0.8rem; }
figure { margin: 0; width: 320px; }
figure img { width: 100%; background: #fff; border-radius: 4px; }
figcaption { font-size: 0.75rem; color: #999; word-break: break-all; padding-top: 0.2rem; }
.counts { color: #888; font-size: 0.85rem; }
"""


def scan_images(root: Path = REPO_ROOT) -> dict:
    """Manifest dict from the on-disk image trees: domain -> script -> entries.

    ``group`` is the sub-directory within the script's image dir (e.g. the per-source
    subfolders ``parametric`` / ``delaunay``), "" at the top level. Paths are POSIX and
    relative to ``root``.
    """
    manifest: dict = {}
    for images_dir in sorted(root.glob("scripts/*/images")):
        domain = images_dir.parent.name
        for script_dir in sorted(p for p in images_dir.iterdir() if p.is_dir()):
            entries = []
            for f in sorted(script_dir.rglob("*")):
                if f.suffix not in (".png", ".fits"):
                    continue
                group = f.parent.relative_to(script_dir).as_posix()
                entries.append(
                    {
                        "file": f.relative_to(root).as_posix(),
                        "kind": f.suffix.lstrip("."),
                        "group": "" if group == "." else group,
                    }
                )
            if entries:
                manifest.setdefault(domain, {})[script_dir.name] = entries
    return manifest


def _pngs(entries):
    return [e for e in entries if e["kind"] == "png"]


def _count(manifest, kind):
    return sum(
        1
        for scripts in manifest.values()
        for es in scripts.values()
        for e in es
        if e["kind"] == kind
    )


def render_html(manifest: dict, root: Path = REPO_ROOT, embed: bool = False) -> str:
    lines = [
        "<meta charset='utf-8'><title>PyAutoGalaxy Visualization Gallery</title>",
        f"<style>{CSS}</style>",
        "<h1>PyAutoGalaxy Visualization Gallery</h1>",
        f"<p class='counts'>{_count(manifest, 'png')} figures (.png) · "
        f"{_count(manifest, 'fits')} data products (.fits, listed in the manifest only) · "
        f"source: <code>scripts/&lt;domain&gt;/images/</code></p>",
    ]
    for domain, scripts in manifest.items():
        lines.append(f"<h2>{html.escape(domain)}</h2>")
        for script, entries in scripts.items():
            pngs = _pngs(entries)
            if not pngs:
                continue
            lines.append(f"<h3>{html.escape(script)} ({len(pngs)} figures)</h3>")
            lines.append("<div class='grid'>")
            for e in pngs:
                if embed:
                    data = base64.b64encode((root / e["file"]).read_bytes()).decode()
                    src = f"data:image/png;base64,{data}"
                else:
                    src = "../../" + e["file"]
                caption = (e["group"] + "/" if e["group"] else "") + Path(e["file"]).name
                lines.append(
                    f"<figure><img loading='lazy' src='{html.escape(src)}'>"
                    f"<figcaption>{html.escape(caption)}</figcaption></figure>"
                )
            lines.append("</div>")
    return "\n".join(lines) + "\n"


def _anchor(text: str) -> str:
    """GitHub's heading-anchor slug: lowercase, drop punctuation, spaces -> '-'."""
    slug = re.sub(r"[^\w\- ]", "", text.strip().lower())
    return slug.replace(" ", "-")


def _group_title(group: str) -> str:
    return f"{group}/" if group else "top level"


def render_markdown(manifest: dict, version: str) -> str:
    """The tracked GALLERY.md: one H2 per domain, H3 per script, H4 per group, H5 per
    figure. Headings carry a ``domain / script`` prefix so every anchor is unique."""
    n_png = _count(manifest, "png")
    lines = [
        "# PyAutoGalaxy Visualization Gallery",
        "",
        "<!-- Generated by gallery/gallery_build.py from scripts/<domain>/images/. "
        "Do not edit by hand: rerun `bash gallery/gallery_run.sh --all`. -->",
        "",
        f"{VERSION_LINE_PREFIX} `{version}` · {n_png} figures.",
        "",
        "Every figure below is what `VisualizerImaging` / `VisualizerInterferometer` / "
        "`VisualizerEllipse` write to a model-fit's `image/` folder, rendered on this repo's "
        "datasets with the true model. See [README.md](README.md) for how to improve one.",
        "",
        "## Contents",
        "",
    ]
    body: list[str] = []
    for domain, scripts in manifest.items():
        lines.append(f"- [{domain}](#{_anchor(domain)})")
        body += ["", f"## {domain}"]
        for script, entries in scripts.items():
            pngs = _pngs(entries)
            if not pngs:
                continue
            h3 = f"{domain} / {script}"
            lines.append(f"  - [{script}](#{_anchor(h3)}) ({len(pngs)} figures)")
            body += ["", f"### {h3}"]
            groups: dict[str, list] = {}
            for e in pngs:
                groups.setdefault(e["group"], []).append(e)
            for group in sorted(groups, key=lambda g: (g != "", g)):
                h4 = f"{domain} / {script} / {_group_title(group)}"
                lines.append(f"    - [{_group_title(group)}](#{_anchor(h4)})")
                body += ["", f"#### {h4}"]
                for e in groups[group]:
                    name = Path(e["file"]).stem
                    body += ["", f"##### {name}", "", f"![{name}]({e['file']})"]
    return "\n".join(lines + body) + "\n"


def stack_versions(autogalaxy_override: str | None = None) -> dict:
    """``{package: __version__}`` for the rendering stack; "unknown" when a package
    does not import (a missing stack must not block a --check)."""
    versions = {}
    for name in STACK:
        if name == "autogalaxy" and autogalaxy_override:
            versions[name] = autogalaxy_override
            continue
        try:
            versions[name] = str(__import__(name).__version__)
        except Exception:  # noqa: BLE001
            versions[name] = "unknown"
    return versions


def figure_entries(manifest: dict, root: Path = REPO_ROOT) -> list[dict]:
    """One mtime-free record per PNG figure, in scan order."""
    figures = []
    for domain, scripts in manifest.items():
        for script, entries in scripts.items():
            for e in _pngs(entries):
                data = (root / e["file"]).read_bytes()
                figures.append(
                    {
                        "file": e["file"],
                        "producer": f"scripts/{domain}/{script}.py",
                        "domain": domain,
                        "source": e["group"],
                        "bytes": len(data),
                        "sha256": hashlib.sha256(data).hexdigest(),
                    }
                )
    return figures


def build_figure_manifest(
    manifest: dict,
    rendered_with: dict,
    previous: dict | None = None,
    root: Path = REPO_ROOT,
    today: str | None = None,
) -> dict:
    """The tracked ``gallery/viz_manifest.yaml`` document.

    ``generated`` / ``rendered_with`` are kept from ``previous`` when the figures and
    the stack are unchanged, so an idempotent rebuild writes identical bytes."""
    figures = figure_entries(manifest, root)
    if (
        previous
        and previous.get("figures") == figures
        and previous.get("rendered_with") == rendered_with
        and previous.get("generated")
    ):
        generated = previous["generated"]
    else:
        generated = today or datetime.date.today().isoformat()
    return {
        "schema": MANIFEST_SCHEMA,
        "generated": str(generated),
        "rendered_with": rendered_with,
        "figure_count": len(figures),
        "figures": figures,
    }


def dump_manifest(doc: dict) -> str:
    return (
        "# Generated by gallery/gallery_build.py — the tracked figure manifest read by\n"
        "# the PyAutoEyes dashboard. Do not edit by hand: rerun\n"
        "# `bash gallery/gallery_run.sh --all` (or `python gallery/gallery_build.py`).\n"
        + yaml.safe_dump(doc, sort_keys=False)
    )


def load_manifest(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        doc = yaml.safe_load(path.read_text())
    except yaml.YAMLError:
        return None
    return doc if isinstance(doc, dict) else None


def _strip_volatile(doc: dict) -> dict:
    return {k: v for k, v in doc.items() if k not in VOLATILE_KEYS}


def _normalise_version_line(text: str) -> str:
    return "\n".join(
        f"{VERSION_LINE_PREFIX} <version>" + line.split("`", 2)[-1]
        if line.startswith(VERSION_LINE_PREFIX)
        else line
        for line in text.splitlines()
    )


def autogalaxy_version() -> str:
    try:
        import autogalaxy

        return autogalaxy.__version__
    except Exception:  # noqa: BLE001 — a missing stack must not block a --check
        return "unknown"


def check(manifest: dict, root: Path = REPO_ROOT) -> list[str]:
    """Problems: unresolvable manifest entries, on-disk images missing from the
    manifest, and a committed GALLERY.md or tracked gallery/viz_manifest.yaml that
    differs from a regeneration."""
    problems = []
    listed = set()
    for scripts in manifest.values():
        for entries in scripts.values():
            for e in entries:
                listed.add(e["file"])
                if not (root / e["file"]).is_file():
                    problems.append(f"manifest entry missing on disk: {e['file']}")
    on_disk = {
        f.relative_to(root).as_posix()
        for f in root.glob("scripts/*/images/**/*")
        if f.suffix in (".png", ".fits")
    }
    for f in sorted(on_disk - listed):
        problems.append(f"on disk but not in manifest: {f}")

    md_path = root / GALLERY_MD
    if not md_path.is_file():
        problems.append(f"{GALLERY_MD} missing — run python gallery/gallery_build.py")
    else:
        expected = render_markdown(manifest, version="<version>")
        if _normalise_version_line(md_path.read_text()) != _normalise_version_line(expected):
            problems.append(
                f"{GALLERY_MD} is stale (figure set changed) — rerun "
                "python gallery/gallery_build.py and commit it"
            )

    tracked = load_manifest(root / TRACKED_MANIFEST)
    if tracked is None:
        problems.append(
            f"{TRACKED_MANIFEST.as_posix()} missing or unreadable — run "
            "python gallery/gallery_build.py and commit it"
        )
    else:
        expected_doc = build_figure_manifest(manifest, rendered_with={}, root=root)
        if _strip_volatile(tracked) != _strip_volatile(expected_doc):
            listed_files = {f.get("file") for f in tracked.get("figures") or []}
            actual = {f["file"]: f for f in expected_doc["figures"]}
            tracked_by_file = {f.get("file"): f for f in tracked.get("figures") or []}
            detail = sorted(
                [f"added {f}" for f in actual.keys() - listed_files]
                + [f"removed {f}" for f in listed_files - actual.keys()]
                + [
                    f"changed {f}"
                    for f in actual.keys() & listed_files
                    if tracked_by_file[f] != actual[f]
                ]
            )
            problems.append(
                f"{TRACKED_MANIFEST.as_posix()} is stale vs the images on disk"
                + (
                    f" ({len(detail)}: {', '.join(detail[:5])}"
                    + (", ..." if len(detail) > 5 else "")
                    + ")"
                    if detail
                    else ""
                )
                + " — rerun python gallery/gallery_build.py and commit it"
            )
    return problems


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--embed", action="store_true")
    parser.add_argument(
        "--root", type=Path, default=REPO_ROOT, help="Repo root to scan (default: this repo)."
    )
    parser.add_argument(
        "--version-string",
        default=None,
        help="PyAutoGalaxy version for the GALLERY.md header (default: autogalaxy.__version__).",
    )
    args = parser.parse_args(argv)
    root = args.root.resolve()

    manifest = scan_images(root)
    if not manifest:
        print("No images found under scripts/*/images — run gallery/gallery_run.sh first.")
        return 1

    gallery_path = root / "output" / "gallery"
    gallery_path.mkdir(parents=True, exist_ok=True)
    (gallery_path / "gallery.html").write_text(render_html(manifest, root))
    if args.embed:
        (gallery_path / "gallery_embedded.html").write_text(render_html(manifest, root, embed=True))

    tracked_path = root / TRACKED_MANIFEST
    if args.check:
        # The gitignored copy mirrors whatever is tracked; --check never rewrites it.
        tracked_text = tracked_path.read_text() if tracked_path.is_file() else None
    else:
        version = args.version_string or autogalaxy_version()
        (root / GALLERY_MD).write_text(render_markdown(manifest, version))
        doc = build_figure_manifest(
            manifest,
            rendered_with=stack_versions(args.version_string),
            previous=load_manifest(tracked_path),
            root=root,
        )
        tracked_text = dump_manifest(doc)
        tracked_path.parent.mkdir(parents=True, exist_ok=True)
        tracked_path.write_text(tracked_text)
    if tracked_text is not None:
        (root / OUTPUT_MANIFEST).write_text(tracked_text)

    for domain, scripts in manifest.items():
        for script, entries in scripts.items():
            n_png = sum(1 for e in entries if e["kind"] == "png")
            n_fits = sum(1 for e in entries if e["kind"] == "fits")
            print(f"{domain}/{script}: {n_png} png, {n_fits} fits")
    print(f"\nGallery:  {gallery_path / 'gallery.html'}")
    print(f"Manifest: {tracked_path} (copy: {root / OUTPUT_MANIFEST})")
    if not args.check:
        print(f"Markdown: {root / GALLERY_MD}")

    if args.check:
        problems = check(manifest, root)
        if problems:
            print("\nCHECK FAILED:")
            for p in problems:
                print(f"  {p}")
            return 1
        print(
            "check: images resolve on disk; GALLERY.md and "
            f"{TRACKED_MANIFEST.as_posix()} are current."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
