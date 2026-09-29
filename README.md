# autogalaxy_visualization

**[Browse the gallery → GALLERY.md](GALLERY.md)**

The permanent, rendered gallery of every figure PyAutoGalaxy writes during a model-fit — the
**galaxy visualization project repo** of the PyAutoLabs organism.

This repo owns the galaxy figures: the producer scripts, the simulators and datasets, the
all-on [`plots.yaml`](config/visualize/plots.yaml), the instrument presets, the tracked PNGs,
[`GALLERY.md`](GALLERY.md) and the render harness. The organ
[PyAutoEyes](https://github.com/PyAutoLabs/PyAutoEyes) is the cross-project visualization
dashboard: it reads this repo's tracked figure manifest
([`gallery/viz_manifest.yaml`](gallery/viz_manifest.yaml)) and links to the PNGs here — it never
renders or copies them. It is the sibling of
[autolens_visualization](https://github.com/PyAutoLabs/autolens_visualization), in the same shape.

## Vision

Until now, the only way to see what a PyAutoGalaxy figure looks like was to run a modelling
script and open its `output/` folder. This repo keeps the most up-to-date rendering of **every**
visualizer output in git — on realistic HST-scale imaging and SMA-scale interferometer data — so
there is one place to see every figure, judge it, and improve it (by hand or in an AI chat
pointed at the plotting source) without re-running anything. Imaging, interferometer and
ellipse (isophote) fitting today; multi-galaxy and multi-dataset (combined) figures next.

Each figure is exactly what `VisualizerImaging` / `VisualizerInterferometer` /
`VisualizerEllipse` write to a fit's `image/` folder, rendered with the simulator's true model —
for imaging and interferometer a parametric (Sersic bulge + Exponential disk) galaxy and a
Delaunay pixelized galaxy; for ellipse fitting a plain ellipse, an m=4 multipole, a scaled m=4
multipole and a tight-mask ellipse — with every toggle in
[`config/visualize/plots.yaml`](config/visualize/plots.yaml) switched on.

## Render locally

```bash
source activate.sh                  # library checkouts on PYTHONPATH (see the file)
bash gallery/gallery_run.sh --all   # run every producer, rebuild GALLERY.md + manifest, --check
```

Or one domain: `python scripts/imaging/visualization.py`, then `python gallery/gallery_build.py`.
Commit the regenerated PNGs under `scripts/<domain>/images/` together with `GALLERY.md` and
`gallery/viz_manifest.yaml` (every figure's producer, domain, source type, path, byte size and
sha256, plus the stack versions it was rendered with). On every PyAutoGalaxy release,
[`render.yml`](.github/workflows/render.yml) re-renders with the released stack, commits the
result and pings PyAutoEyes (`repository_dispatch: eyes-refresh`) to refresh its dashboard.

Runtime on an 8-core laptop (CPU, NumPy path): imaging ~35 s, interferometer ~30 s, ellipse
~20 s (the masked scenario keeps the full 300-iteration mask-rejection loop and still renders in
about 4 s at HST scale).

## Add a domain

- Add a simulator (or instrument preset) under `scripts/misc/simulators/` and track its dataset
  under `dataset/<domain>/<instrument>/`.
- Add a flat producer `scripts/<domain>/visualization.py` modelled on
  [`scripts/imaging/visualization.py`](scripts/imaging/visualization.py).
- Run `bash gallery/gallery_run.sh --all` and commit the PNGs + `GALLERY.md` +
  `gallery/viz_manifest.yaml`.

## Improve a figure

Three edit surfaces, from cheapest to deepest:

- **Config** — [`config/visualize/plots.yaml`](config/visualize/plots.yaml): which figures are
  written at all.
- **Plot API** — the plotting code in the libraries: `PyAutoGalaxy/autogalaxy/**/plot/`,
  `PyAutoArray/autoarray/plot/`. Change it there (normal library workflow), then re-render here.
- **Script** — the producer in `scripts/<domain>/visualization.py` (dataset, model, source types).

The Brain Eyes agent runs the review loop on this repo:
`bin/pyauto-brain eyes survey galaxy/autogalaxy_visualization` (or `/eyes review galaxy`).
Accepted critiques are filed with the `eyes-critique` label.

## Related repos

- [PyAutoEyes](https://github.com/PyAutoLabs/PyAutoEyes) — the organ: the cross-project
  visualization dashboard that aggregates this repo (reads `gallery/viz_manifest.yaml`, links to
  the PNGs here).
- [autolens_visualization](https://github.com/PyAutoLabs/autolens_visualization) — the lens
  sibling this repo mirrors (and the source of its instrument presets and harness).
- [autogalaxy_workspace](https://github.com/PyAutoLabs/autogalaxy_workspace) — user-facing
  science scripts and tutorials.
- [autogalaxy_workspace_test](https://github.com/PyAutoLabs/autogalaxy_workspace_test) —
  visualization tests (file / FITS-HDU assertions) the producers here were ported from.

## Community & support

- **Slack** — [PyAutoLens workspace](https://join.slack.com/t/pyautolens/shared_invite/zt-2cufp4eyf-fXfgMxRGuvg~bMrI3uOAxg) for questions (it hosts PyAutoGalaxy too).
- **Issues** — file figure bugs and visualization requests on this repo's [issue tracker](https://github.com/PyAutoLabs/autogalaxy_visualization/issues).
