"""
Visualization: Interferometer
=============================

Renders every figure ``VisualizerInterferometer`` writes during a real PyAutoGalaxy
model-fit, on the SMA-preset interferometer dataset, so the most up-to-date version of
each figure lives in git and can be browsed on GitHub (``GALLERY.md``) without
re-running a fit.

This script RENDERS, it does not test: there are no assertions on file names or FITS
HDUs (that is ``autogalaxy_workspace_test``'s job). Which figures appear is governed by
``config/visualize/plots.yaml`` (every toggle on).

Output tree (wiped at the start of every run so stale PNGs never linger)::

    scripts/interferometer/images/visualization/
        dataset.png, adapt_images.png   <- visualize_before_fit
        parametric/   <- visualize(), Sersic bulge + Exponential disk galaxy
        delaunay/     <- visualize(), Delaunay pixelized galaxy (Overlay image-mesh)

The FITS / CSV products the visualizer also writes are gitignored; only PNGs are tracked.

Dataset: ``dataset/interferometer/sma`` (190 visibilities, 256x256 real-space grid at
0.1"/pix, circular real-space mask 3.5", exact DFT transformer), simulated by
``scripts/misc/simulators/interferometer.py --instrument sma`` with the same galaxy as
the imaging dataset. The model is that TRUE model.

Ported from ``autogalaxy_workspace_test/scripts/interferometer/visualization/
visualization.py`` (which renders one MGE galaxy with no before-fit call); here the
simulator's true Sersic + Exponential galaxy and a Delaunay galaxy are rendered, plus
``visualize_before_fit``, mirroring the imaging producer.

Run from the repo root::

    python scripts/interferometer/visualization.py
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
    output_path=str(REPO_ROOT / "scripts" / "interferometer" / "images"),
)

import autofit as af
import autogalaxy as ag
from autogalaxy.interferometer.model.visualizer import VisualizerInterferometer

from _viz_cli import auto_simulate_if_missing
from instruments.interferometer import INSTRUMENTS

INSTRUMENT = "sma"

"""
__Dataset__

The SMA preset: a circular real-space mask on the preset's real-space grid, and the
exact DFT transformer (190 visibilities make the DFT cheap).
"""
config = INSTRUMENTS[INSTRUMENT]
dataset_path = REPO_ROOT / "dataset" / "interferometer" / INSTRUMENT

auto_simulate_if_missing(
    dataset_path, dataset_type="interferometer", instrument=INSTRUMENT, workspace_root=REPO_ROOT
)

real_space_mask = ag.Mask2D.circular(
    shape_native=config["real_space_shape"],
    pixel_scales=config["pixel_scale"],
    radius=config["mask_radius"],
)

dataset = ag.Interferometer.from_fits(
    data_path=dataset_path / "data.fits",
    noise_map_path=dataset_path / "noise_map.fits",
    uv_wavelengths_path=dataset_path / "uv_wavelengths.fits",
    real_space_mask=real_space_mask,
    transformer_class=ag.TransformerDFT,
)

"""
__True Model__

Restated verbatim from ``scripts/misc/simulators/interferometer.py``: one galaxy at
z=0.5 with a Sersic bulge and an Exponential disk. Every parameter is fixed, so the
prior-median instance IS the true model.
"""
galaxy_parametric = af.Model(
    ag.Galaxy,
    redshift=0.5,
    bulge=ag.lp.Sersic(
        centre=(0.0, 0.0),
        ell_comps=ag.convert.ell_comps_from(axis_ratio=0.9, angle=45.0),
        intensity=2.0,
        effective_radius=0.6,
        sersic_index=3.0,
    ),
    disk=ag.lp.Exponential(
        centre=(0.0, 0.0),
        ell_comps=ag.convert.ell_comps_from(axis_ratio=0.7, angle=30.0),
        intensity=1.0,
        effective_radius=1.6,
    ),
)

model_parametric = af.Collection(galaxies=af.Collection(galaxy=galaxy_parametric))

"""
__Delaunay Galaxy__

The galaxy's light replaced by a Delaunay pixelization whose vertices come from an
``Overlay`` image-mesh over the real-space mask, regularized by ``ConstantSplit``.
"""
image_mesh = ag.image_mesh.Overlay(shape=(26, 26))
image_plane_mesh_grid = image_mesh.image_plane_mesh_grid_from(mask=real_space_mask)

pixelization = ag.Pixelization(
    mesh=ag.mesh.Delaunay(pixels=image_plane_mesh_grid.shape[0], zeroed_pixels=0),
    regularization=ag.reg.ConstantSplit(coefficient=1.0),
)
galaxy_delaunay = af.Model(ag.Galaxy, redshift=0.5, pixelization=pixelization)

model_delaunay = af.Collection(galaxies=af.Collection(galaxy=galaxy_delaunay))

"""
__Adapt Images__

Built from the real-space per-galaxy image of the parametric (true-model) fit; the
Overlay mesh grid is attached to the galaxy.
"""
instance_parametric = model_parametric.instance_from_prior_medians()

fit_parametric = ag.FitInterferometer(dataset=dataset, galaxies=list(instance_parametric.galaxies))

adapt_images = ag.AdaptImages(
    galaxy_name_image_dict={
        "('galaxies', 'galaxy')": fit_parametric.galaxy_image_dict[
            instance_parametric.galaxies.galaxy
        ],
    },
    galaxy_name_image_plane_mesh_grid_dict={"('galaxies', 'galaxy')": image_plane_mesh_grid},
)

analysis = ag.AnalysisInterferometer(dataset=dataset, adapt_images=adapt_images, use_jax=False)

"""
__Paths__

``VisualizerInterferometer`` only needs ``image_path`` and ``output_path``. The image
tree is wiped first so the committed PNG set is exactly what this run produced.
"""
image_path = REPO_ROOT / "scripts" / "interferometer" / "images" / "visualization"
if image_path.exists():
    shutil.rmtree(image_path)
image_path.mkdir(parents=True)

scratch_root = REPO_ROOT / "output" / "visualization" / "interferometer"
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

dataset.png, adapt_images.png (+ gitignored FITS).
"""
t0 = time.perf_counter()
VisualizerInterferometer.visualize_before_fit(
    analysis=analysis, paths=_paths(None), model=model_parametric
)
print(f"visualize_before_fit: {time.perf_counter() - t0:.1f}s")

"""
__Visualize (per source)__

fit, dirty images, real space, galaxies (+ inversion for Delaunay).
"""
for name, model in (("parametric", model_parametric), ("delaunay", model_delaunay)):
    t0 = time.perf_counter()
    VisualizerInterferometer.visualize(
        analysis=analysis,
        paths=_paths(name),
        instance=model.instance_from_prior_medians(),
        during_analysis=False,
    )
    print(f"visualize [{name}]: {time.perf_counter() - t0:.1f}s")

n_png = len(list(image_path.rglob("*.png")))
print(f"Wrote {n_png} PNGs under {image_path.relative_to(REPO_ROOT)}")
