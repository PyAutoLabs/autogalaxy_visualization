# autogalaxy_visualization — Agent Instructions

This repo is the single home for **what PyAutoGalaxy figures look like**: it stores, in git, the
most up-to-date rendering of every figure the PyAutoGalaxy visualizers write during a model-fit,
on realistic HST-scale imaging and SMA-scale interferometer data, so visualization can be judged
and improved (by humans or AI chats against the source) without re-running a workspace fit. It is
a collection of standalone producer scripts, **not** an installable package — there is no
`pyproject.toml`. These are the canonical, agent-agnostic instructions for this repo; the
`README.md` is the human-facing overview and `GALLERY.md` is the browsable gallery. It is the
galaxy sibling of `lens/autolens_visualization` and mirrors its layout exactly.

## Layering: project repo vs organ

This is a **project repo** (category `project`, like `autolens_visualization`): it makes, stores
and tracks the galaxy figures — producers, simulators, datasets, `plots.yaml`, instruments,
tracked PNGs, `GALLERY.md`, the render harness. The organ **PyAutoEyes** is the cross-project
visualization dashboard over the `<lib>_visualization` project repos: it reads this repo's
tracked `gallery/viz_manifest.yaml` and links to the PNGs here; it renders nothing and copies no
figures. Judging figures is the Brain's Eyes conductor; figure changes land here (producer /
config) or in the libraries (plot API), never in the organ.

## Repository Structure

Producers are laid out **flat, one per domain** (`scripts/<domain>/visualization*.py`), because
the Brain Eyes agent scans `scripts/<domain>/*.py` non-recursively for stems containing
`visualization`:

```
scripts/
  imaging/visualization.py          VisualizerImaging on dataset/imaging/hst
  imaging/images/visualization/     its output: before-fit PNGs + parametric/ + delaunay/
  interferometer/visualization.py   VisualizerInterferometer on dataset/interferometer/sma
  interferometer/images/visualization/
  ellipse/visualization.py          VisualizerEllipse on dataset/imaging/hst
  ellipse/images/visualization/     before-fit + plain/ multipole/ multipole_scaled/ masked/
  misc/simulators/                  imaging.py + interferometer.py (regenerate datasets)
  misc/test/                        hermetic pytest for the gallery builder
gallery/gallery_build.py            GALLERY.md + gallery/viz_manifest.yaml + output/gallery/
gallery/viz_manifest.yaml           TRACKED, generated figure manifest (PyAutoEyes read contract)
gallery/gallery_run.sh              run producers -> build -> --check
config/general.yaml                 layered over the library config (version check off)
config/visualize/plots.yaml         the library default with EVERY toggle on
instruments/                        imaging + interferometer presets (copied from autolens_visualization)
dataset/imaging/hst/                TRACKED, simulated here (Sersic bulge + Exponential disk)
dataset/interferometer/sma/         TRACKED, simulated here (190 visibilities, same galaxy)
_viz_cli.py                         repo-root finder, dataset paths, auto-simulate hook
GALLERY.md                          TRACKED, generated — never edit by hand
```

**What is tracked.** PNG figures under `scripts/<domain>/images/**`, `GALLERY.md`,
`gallery/viz_manifest.yaml` and the datasets (FITS + `galaxies.json`). The FITS / CSV / JSON data
products the visualizers also write are gitignored (bulky, not viewable on GitHub), as is
`output/`.

**Import model.** Producers find the repo root by walking up to the directory containing
`ruff.toml` (a depth-proof sentinel) and put it on `sys.path`, so `_viz_cli` and `instruments`
import by their top-level names.

## Rendering

From the repo root, with the library checkouts on `PYTHONPATH` (`source activate.sh`):

```bash
bash gallery/gallery_run.sh --all        # every producer, then build + --check (~90 s)
python scripts/imaging/visualization.py  # one producer (~35 s)
python gallery/gallery_build.py          # rebuild GALLERY.md + gallery/viz_manifest.yaml + output/gallery/
python gallery/gallery_build.py --check  # fail if GALLERY.md or the manifest is stale vs the PNGs on disk
```

Each producer wipes its own `scripts/<domain>/images/visualization/` tree first, so the committed
PNG set is exactly what the last run produced. Commit the PNGs, `GALLERY.md` and
`gallery/viz_manifest.yaml` together.

**The tracked manifest** (`gallery/viz_manifest.yaml`, schema 1) lists every committed PNG as
`{file, producer, domain, source, bytes, sha256}` (`source` = the per-source sub-folder —
`parametric` / `delaunay` for imaging and interferometer, `plain` / `multipole` /
`multipole_scaled` / `masked` for ellipse — or `""` for the before-fit figures), plus
`rendered_with:` (the autogalaxy / autoarray / autofit versions) and `generated:` (the date the
figures or stack last changed — carried over on an unchanged rebuild, so re-running is a git
no-op). There are no mtimes: it is reproducible from a checkout. `--check` ignores only
`generated:` and `rendered_with:`; any added, removed or byte-changed PNG fails it. It is the
read contract of the PyAutoEyes dashboard — change its shape only together with the organ.

Each producer pushes `config/` via `conf.instance.push` (the all-true `plots.yaml`), loads its
tracked dataset, builds the simulator's **true model** (every parameter fixed), and calls
`Visualizer*.visualize_before_fit` once and `Visualizer*.visualize` once per source type
(`parametric/` = Sersic bulge + Exponential disk, `delaunay/` = Overlay image-mesh + `Delaunay`
+ `ConstantSplit`; for ellipse, one call per scenario), with a
`SimpleNamespace(image_path=..., output_path=...)` paths stub. The adapt image is the galaxy
image of the parametric fit, keyed `('galaxies', 'galaxy')`.

**Toggles no PyAutoGalaxy plotter reads (yet).** `fit.subplot_fit_log10`,
`fit.subplot_galaxy_images` and `inversion.subplot_mappings` are true in `plots.yaml` but the
PyAutoGalaxy plotters do not consult them today, so no `fit_log10.png` or mappings figure
appears. `visualize_combined` / `visualize_before_fit_combined` are not rendered: they need
several analyses (a multi-dataset fit). In the ellipse domain the `data`, `data_no_ellipse` and
log10 variants all write `ellipse_fit.png`, so only the last-written variant survives — a
library-side naming collision, visible in the gallery.

**Datasets.** Both were produced by this repo's simulators:

```bash
python scripts/misc/simulators/imaging.py --instrument hst
python scripts/misc/simulators/interferometer.py --instrument sma
```

One galaxy at z=0.5 (Sersic bulge I=2.0, R=0.6", n=3 + Exponential disk I=1.0, R=1.6") in both.
The SMA visibilities are transformed from the preset's 3.5" circular real-space mask (the one
the producer fits with) with no over-sampling, because the disk extends past the mask and the
Interferometer dataset evaluates light profiles at sub-size 1 — so the true-model residuals are
noise. The `sma` preset's `noise_sigma` is 10.0 (autolens_profiling: 1000.0), so the dirty image
shows the galaxy instead of pure noise. The ellipse producer reuses the imaging dataset (the PSF
is ignored by ellipse fitting). The auto-simulate hook in `_viz_cli.py` only fires when
`data.fits` is absent — it never deletes a tracked dataset.

## Adding a domain

1. Add a simulator under `scripts/misc/simulators/` (or an instrument preset) and track its
   dataset under `dataset/<domain>/<instrument>/`.
2. Add a flat producer `scripts/<domain>/visualization.py` modelled on the imaging one, writing
   to `scripts/<domain>/images/visualization/`.
3. Run `bash gallery/gallery_run.sh --all` and commit the PNGs + `GALLERY.md` +
   `gallery/viz_manifest.yaml`.

## Improving a figure (edit surfaces)

- **config** — `config/visualize/plots.yaml` here: which figures are written at all.
- **plot API** — the plotting code in the libraries: `PyAutoGalaxy/autogalaxy/**/plot/`,
  `PyAutoArray/autoarray/plot/` (library changes go through the normal library workflow, then
  this repo is re-rendered).
- **script** — the producer in `scripts/<domain>/visualization.py` (dataset, model, source types).

## Eyes contracts

Two readers depend on this repo's layout:

- **The Brain Eyes conductor** (`organs/PyAutoBrain/agents/conductors/eyes/`) reviews it:
  `bin/pyauto-brain eyes survey galaxy/autogalaxy_visualization` (or `/eyes review galaxy`). It
  expects flat `scripts/<domain>/visualization*.py` producers writing
  `scripts/<domain>/images/<stem>/**`, a `gallery/gallery_run.sh` harness, and
  `output/gallery/{gallery.html,viz_manifest.yaml}` (the latter a gitignored copy of the tracked
  manifest). Accepted critiques are labelled `eyes-critique` and route through intake /
  start_dev like any other change.
- **The PyAutoEyes dashboard** reads the tracked `gallery/viz_manifest.yaml` and links to the
  PNGs; `render.yml` fires `repository_dispatch: eyes-refresh` at PyAutoLabs/PyAutoEyes after
  each release re-render.

Keep that layout when adding domains.

## Testing

The PR gate is `lint.yml` on Python 3.12 against the library mains (PyAutoNerves, PyAutoFit,
PyAutoArray, PyAutoGalaxy):

```bash
ruff check .
ruff format --check .
python gallery/gallery_build.py --check
pytest scripts/misc/test -q
```

plus `lychee` on every `*.md`, then every producer runs for real followed by
`gallery_build.py --check` (a PR that changes the figure set without regenerating `GALLERY.md`
fails). `render.yml` (manual + `repository_dispatch: pyautogalaxy-release`) re-renders with the
released PyPI stack, commits PNGs + `GALLERY.md` + `gallery/viz_manifest.yaml` back as
`github-actions[bot]` `[skip ci]`, then dispatches `eyes-refresh` to PyAutoEyes (token:
`secrets.PAT_PYAUTOLABS`; the step warns and skips when the secret is unavailable).

## Sandboxed / restricted runs

```bash
NUMBA_CACHE_DIR=/tmp/numba_cache MPLCONFIGDIR=/tmp/matplotlib python scripts/imaging/visualization.py
```

## Bulk-edit safety

When editing the same region across many scripts in one pass, only rewrite the targeted region.
**Never produce a whole-file write unless you have read the entire current file.**

## Related Repos

- `../PyAutoGalaxy` — the visualizers being rendered (plus `../../array/PyAutoArray`,
  `../../fit/PyAutoFit`, `../../organs/PyAutoNerves` on `PYTHONPATH`).
- `../autogalaxy_workspace` — user-facing science scripts and tutorials.
- `../autogalaxy_workspace_test` — visualization *tests* (file/HDU assertions) the producers
  here were ported from.
- `../../lens/autolens_visualization` — the lens sibling this repo mirrors; source of the
  instrument presets, the gallery harness and the builder.
- `../../organs/PyAutoEyes` — the organ: cross-project visualization dashboard that aggregates
  this repo via `gallery/viz_manifest.yaml` (links to the PNGs, never copies them).

## Task Workflows

When changing a producer, the config or a dataset, re-render (`gallery/gallery_run.sh --all`),
keep `ruff check .` / `ruff format --check .` clean, and commit the PNGs + `GALLERY.md` +
`gallery/viz_manifest.yaml` in the same PR. Do not commit machine-specific absolute paths.

<!-- repos_sync:history:begin -->
## Never rewrite history

Never rewrite pushed history on any repo with a remote — no `git init` over a
tracked repo, no force-push to `main`, no fresh-start "Initial commit", no
`filter-repo` / `filter-branch` / `rebase -i` on pushed branches. To get a
clean tree: `git fetch origin && git reset --hard origin/main && git clean -fd`.
<!-- repos_sync:history:end -->

<!-- repos_sync:deliverable:begin -->
## Sessions end at their deliverable

A session ends when it reports its deliverable — never arm anything that
outlives the turn to wait for CI, a review or a merge: no `send_later`, no
`subscribe_pr_activity`, no `CronCreate`, no `ScheduleWakeup`, no `/loop`, no
`RemoteTrigger` create/update/run. Judge once, report, stop; the human re-runs
`/prm` (or the batch review) when it is green. Measured: five batch members
armed hourly check-ins on 2026-08-31, and a mobile `/prm` re-armed a 60-minute
`send_later` hourly all night on 2026-09-03 with no task active, draining usage.
<!-- repos_sync:deliverable:end -->

<!-- repos_sync:filing:begin -->
## Where to file

Questions, help with code or an analysis, ideas, bug reports and results from a
user or collaborator — or an agent acting for one — go to
<https://github.com/orgs/PyAutoLabs/discussions> in the matching category
(Help & Questions, Ideas & Proposals, Bugs & Errors, Show and tell;
Announcements is maintainers-only), never to this repo's Issues. An agent never
runs `gh issue create` for such a report: it drafts the title, category and
body and hands them to the human (sessions cannot create Discussions). Only the
development flow — Mind prompt → `/start_dev` → `/create_issue` → one issue per
task → PR — opens issues here. Why: `PyAutoMind/policy/community_surface.md`.
<!-- repos_sync:filing:end -->

<!-- repos_sync:standards:begin -->
## Shared standards

Before changing a shared interface, consult the applicable
[organism standard](https://github.com/PyAutoLabs/PyAutoBrain/blob/main/docs/standards.md)
on demand, identify affected consumers, and validate their adoption. Change
generated guidance at its canonical source and regenerate.
<!-- repos_sync:standards:end -->
