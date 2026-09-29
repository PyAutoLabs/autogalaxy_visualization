"""
Visualization: Ellipse
======================

Renders every figure ``VisualizerEllipse`` writes during a real PyAutoGalaxy ellipse
(isophote) fit, on the HST-scale imaging dataset, so the most up-to-date version of each
figure lives in git and can be browsed on GitHub (``GALLERY.md``) without re-running a
fit.

This script RENDERS, it does not test: there are no assertions on file names or FITS
HDUs (that is ``autogalaxy_workspace_test``'s job). Which figures appear is governed by
``config/visualize/plots.yaml`` (every toggle on).

Output tree (wiped at the start of every run so stale PNGs never linger)::

    scripts/ellipse/images/visualization/
        dataset.png          <- visualize_before_fit
        plain/               <- visualize(), one Ellipse, no perturbation
        multipole/           <- visualize(), Ellipse + EllipseMultipole (m=4)
        multipole_scaled/    <- visualize(), Ellipse + EllipseMultipoleScaled (m=4)
        masked/              <- visualize(), one Ellipse over a tight 0.95" mask, so the
                                perimeter crosses masked pixels and the mask-rejection
                                loop in ``FitEllipse.points_from_major_axis_from`` fires

The FITS products the visualizer also writes are gitignored; only PNGs are tracked.

Dataset: ``dataset/imaging/hst`` — the same tracked HST imaging the imaging producer
renders (the PSF is ignored by ellipse fitting), masked with the preset's 3.5" circle
for the first three scenarios and a 0.95" circle for ``masked``. The ellipse parameters
are fixed (every model has no free parameters) with a 1.0" major axis, so the
prior-median instance is deterministic. The full 300-iteration mask-rejection loop is
kept: at HST scale the masked scenario renders in seconds.

Ported from ``autogalaxy_workspace_test/scripts/ellipse/visualization/visualization.py``
(the four scenarios and their ellipse / multipole parameters are unchanged; its
``scaled`` sub-folder is named ``multipole_scaled`` here, and ``visualize_before_fit``
runs once at the top level instead of per scenario, like the imaging producer).

Run from the repo root::

    python scripts/ellipse/visualization.py
"""

import shutil
import sys
import time
from pathlib import Path
from types import SimpleNamespace


def _repo_root() -> Path:
    for _p in Path(__file__).resolve().parents:
        if (_p / "ruff.toml").exists():
            return _p
    raise RuntimeError("autogalaxy_visualization root (ruff.toml) not found")


REPO_ROOT = _repo_root()
sys.path.insert(0, str(REPO_ROOT))

# Push the all-true plots.yaml before any visualization code path reads config.
from autogalaxy import conf

conf.instance.push(
    new_path=str(REPO_ROOT / "config"),
    output_path=str(REPO_ROOT / "scripts" / "ellipse" / "images"),
)

import autofit as af
import autogalaxy as ag
from autogalaxy.ellipse.model.visualizer import VisualizerEllipse

from _viz_cli import auto_simulate_if_missing
from instruments.imaging import INSTRUMENTS

INSTRUMENT = "hst"

"""
__Dataset__

The tracked HST imaging, masked twice: the preset's generous 3.5" circle (the 1.0"
ellipse sits well inside it) and a tight 0.95" circle (the ellipse perimeter crosses it).
"""
pixel_scale = INSTRUMENTS[INSTRUMENT]["pixel_scale"]
dataset_path = REPO_ROOT / "dataset" / "imaging" / INSTRUMENT

auto_simulate_if_missing(
    dataset_path, dataset_type="imaging", instrument=INSTRUMENT, workspace_root=REPO_ROOT
)

dataset_unmasked = ag.Imaging.from_fits(
    data_path=dataset_path / "data.fits",
    psf_path=dataset_path / "psf.fits",
    noise_map_path=dataset_path / "noise_map.fits",
    pixel_scales=pixel_scale,
)

mask_generous = ag.Mask2D.circular(
    shape_native=dataset_unmasked.shape_native,
    pixel_scales=dataset_unmasked.pixel_scales,
    radius=INSTRUMENTS[INSTRUMENT]["mask_radius"],
)
dataset_generous = dataset_unmasked.apply_mask(mask=mask_generous)

mask_tight = ag.Mask2D.circular(
    shape_native=dataset_unmasked.shape_native,
    pixel_scales=dataset_unmasked.pixel_scales,
    radius=0.95,
)
dataset_tight = dataset_unmasked.apply_mask(mask=mask_tight)

"""
__Models__

One ``Ellipse`` per model, optionally with a ``multipoles`` collection holding a single
``EllipseMultipole`` or ``EllipseMultipoleScaled``. Every parameter is fixed.
"""


def ellipse_model(major_axis: float):
    ellipse = af.Model(ag.Ellipse)
    ellipse.centre.centre_0 = 0.0
    ellipse.centre.centre_1 = 0.0
    ellipse.ell_comps.ell_comps_0 = 0.1
    ellipse.ell_comps.ell_comps_1 = 0.05
    ellipse.major_axis = major_axis
    return ellipse


def multipole_model(m: int, cos_amp: float, sin_amp: float):
    multipole = af.Model(ag.EllipseMultipole)
    multipole.m = m
    multipole.multipole_comps.multipole_comps_0 = cos_amp
    multipole.multipole_comps.multipole_comps_1 = sin_amp
    return multipole


def scaled_multipole_model(m: int, cos_amp: float, sin_amp: float, major_axis: float):
    multipole = af.Model(ag.EllipseMultipoleScaled)
    multipole.m = m
    multipole.scaled_multipole_comps.scaled_multipole_comps_0 = cos_amp
    multipole.scaled_multipole_comps.scaled_multipole_comps_1 = sin_amp
    multipole.major_axis = major_axis
    return multipole


major_axis = 1.0

model_plain = af.Collection(
    ellipses=af.Collection(ellipse_0=ellipse_model(major_axis=major_axis)),
)

model_multipole = af.Collection(
    ellipses=af.Collection(ellipse_0=ellipse_model(major_axis=major_axis)),
    multipoles=af.Collection(
        ellipse_0=af.Collection(m4=multipole_model(m=4, cos_amp=0.05, sin_amp=0.0)),
    ),
)

model_multipole_scaled = af.Collection(
    ellipses=af.Collection(ellipse_0=ellipse_model(major_axis=major_axis)),
    multipoles=af.Collection(
        ellipse_0=af.Collection(
            m4=scaled_multipole_model(m=4, cos_amp=0.05, sin_amp=0.0, major_axis=major_axis)
        ),
    ),
)

scenarios = (
    ("plain", dataset_generous, model_plain),
    ("multipole", dataset_generous, model_multipole),
    ("multipole_scaled", dataset_generous, model_multipole_scaled),
    ("masked", dataset_tight, model_plain),
)

"""
__Paths__

``VisualizerEllipse`` only needs ``image_path`` and ``output_path``. The image tree is
wiped first so the committed PNG set is exactly what this run produced.
"""
image_path = REPO_ROOT / "scripts" / "ellipse" / "images" / "visualization"
if image_path.exists():
    shutil.rmtree(image_path)
image_path.mkdir(parents=True)

scratch_root = REPO_ROOT / "output" / "visualization" / "ellipse"
if scratch_root.exists():
    shutil.rmtree(scratch_root)


def _paths(sub: str | None) -> SimpleNamespace:
    img = image_path / sub if sub else image_path
    img.mkdir(parents=True, exist_ok=True)
    out = scratch_root / (sub or "before_fit")  # scratch output -> gitignored output/
    out.mkdir(parents=True, exist_ok=True)
    return SimpleNamespace(image_path=img, output_path=out)


"""
__Visualize Before Fit__

dataset.png (+ gitignored FITS), on the generous-mask dataset.
"""
t0 = time.perf_counter()
VisualizerEllipse.visualize_before_fit(
    analysis=ag.AnalysisEllipse(dataset=dataset_generous, use_jax=False),
    paths=_paths(None),
    model=model_plain,
)
print(f"visualize_before_fit: {time.perf_counter() - t0:.1f}s")

"""
__Visualize (per scenario)__

dataset, ellipse_fit, ellipse_residuals, fit_ellipse (+ data_no_ellipse variants).
"""
for name, dataset, model in scenarios:
    t0 = time.perf_counter()
    VisualizerEllipse.visualize(
        analysis=ag.AnalysisEllipse(dataset=dataset, use_jax=False),
        paths=_paths(name),
        instance=model.instance_from_prior_medians(),
        during_analysis=False,
    )
    print(f"visualize [{name}]: {time.perf_counter() - t0:.1f}s")

n_png = len(list(image_path.rglob("*.png")))
print(f"Wrote {n_png} PNGs under {image_path.relative_to(REPO_ROOT)}")
