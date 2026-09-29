"""
Visualization: Imaging
======================

Renders every figure ``VisualizerImaging`` writes during a real PyAutoGalaxy model-fit,
on the HST-scale imaging dataset, so the most up-to-date version of each figure lives
in git and can be browsed on GitHub (``GALLERY.md``) without re-running a fit.

This script RENDERS, it does not test: there are no assertions on file names or FITS
HDUs (that is ``autogalaxy_workspace_test``'s job). Which figures appear is governed by
``config/visualize/plots.yaml`` (every toggle on).

Output tree (wiped at the start of every run so stale PNGs never linger)::

    scripts/imaging/images/visualization/
        dataset.png, adapt_images.png   <- visualize_before_fit
        parametric/   <- visualize(), Sersic bulge + Exponential disk galaxy
        delaunay/     <- visualize(), Delaunay pixelized galaxy (Overlay image-mesh)

The FITS / CSV products the visualizer also writes are gitignored; only PNGs are tracked.

Dataset: ``dataset/imaging/hst`` (0.05"/pix, 141x141, 21x21 Gaussian PSF, circular mask
3.5"), simulated by ``scripts/misc/simulators/imaging.py --instrument hst``. The model is
the simulator's TRUE model, so every figure shows what a user sees in ``output/`` after a
fit that found the right answer.

Ported from ``autogalaxy_workspace_test/scripts/imaging/visualization/visualization.py``
(parametric + Delaunay kept; the rectangular run, the likelihood-sanity asserts and the
RGB ``plot_array`` check are test concerns and are dropped). ``visualize_combined`` is not
rendered: it needs several analyses (a multi-dataset fit) and this repo has one dataset
per domain.

Run from the repo root::

    python scripts/imaging/visualization.py
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
    output_path=str(REPO_ROOT / "scripts" / "imaging" / "images"),
)

import autofit as af
import autogalaxy as ag
from autogalaxy.imaging.model.visualizer import VisualizerImaging

from _viz_cli import auto_simulate_if_missing
from instruments.imaging import INSTRUMENTS

INSTRUMENT = "hst"

"""
__Dataset__

The HST preset: circular 3.5" mask, then radial-bin over-sampling of the light profiles
centred on the galaxy.
"""
pixel_scale = INSTRUMENTS[INSTRUMENT]["pixel_scale"]
dataset_path = REPO_ROOT / "dataset" / "imaging" / INSTRUMENT

auto_simulate_if_missing(
    dataset_path, dataset_type="imaging", instrument=INSTRUMENT, workspace_root=REPO_ROOT
)

dataset = ag.Imaging.from_fits(
    data_path=dataset_path / "data.fits",
    psf_path=dataset_path / "psf.fits",
    noise_map_path=dataset_path / "noise_map.fits",
    pixel_scales=pixel_scale,
)

mask_radius = INSTRUMENTS[INSTRUMENT]["mask_radius"]

mask = ag.Mask2D.circular(
    shape_native=dataset.shape_native,
    pixel_scales=dataset.pixel_scales,
    radius=mask_radius,
)

dataset = dataset.apply_mask(mask=mask)

over_sample_size = ag.util.over_sample.over_sample_size_via_radial_bins_from(
    grid=dataset.grid,
    sub_size_list=[4, 2, 2],
    radial_list=[0.3, 0.6],
    centre_list=[(0.0, 0.0)],
)

dataset = dataset.apply_over_sampling(over_sample_size_lp=over_sample_size)

"""
__True Model__

Restated verbatim from ``scripts/misc/simulators/imaging.py``: one galaxy at z=0.5 with
a Sersic bulge and an Exponential disk. Every parameter is fixed, so the model has no
free parameters and its prior-median instance IS the true model.
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
``Overlay`` image-mesh over the mask, regularized by ``ConstantSplit``.
"""
image_mesh = ag.image_mesh.Overlay(shape=(26, 26))
image_plane_mesh_grid = image_mesh.image_plane_mesh_grid_from(mask=dataset.mask)

pixelization = ag.Pixelization(
    mesh=ag.mesh.Delaunay(pixels=image_plane_mesh_grid.shape[0], zeroed_pixels=0),
    regularization=ag.reg.ConstantSplit(coefficient=1.0),
)
galaxy_delaunay = af.Model(ag.Galaxy, redshift=0.5, pixelization=pixelization)

model_delaunay = af.Collection(galaxies=af.Collection(galaxy=galaxy_delaunay))

"""
__Adapt Images__

Built the way a pipeline builds them: from the per-galaxy model image of the parametric
(true-model) fit. The Overlay mesh grid is attached to the galaxy.
"""
instance_parametric = model_parametric.instance_from_prior_medians()

fit_parametric = ag.FitImaging(dataset=dataset, galaxies=list(instance_parametric.galaxies))
galaxy_model_image_dict = fit_parametric.galaxy_model_image_dict

adapt_images = ag.AdaptImages(
    galaxy_name_image_dict={
        "('galaxies', 'galaxy')": galaxy_model_image_dict[instance_parametric.galaxies.galaxy],
    },
    galaxy_name_image_plane_mesh_grid_dict={"('galaxies', 'galaxy')": image_plane_mesh_grid},
)

analysis = ag.AnalysisImaging(dataset=dataset, adapt_images=adapt_images, use_jax=False)

"""
__Paths__

``VisualizerImaging`` only needs ``image_path`` and ``output_path``. The image tree is
wiped first so the committed PNG set is exactly what this run produced.
"""
image_path = REPO_ROOT / "scripts" / "imaging" / "images" / "visualization"
if image_path.exists():
    shutil.rmtree(image_path)
image_path.mkdir(parents=True)

scratch_root = REPO_ROOT / "output" / "visualization" / "imaging"
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
VisualizerImaging.visualize_before_fit(
    analysis=analysis, paths=_paths(None), model=model_parametric
)
print(f"visualize_before_fit: {time.perf_counter() - t0:.1f}s")

"""
__Visualize (per source)__

fit, fit_log10, of_galaxies, galaxy_images, galaxies (+ inversion and mappings for
Delaunay).
"""
for name, model in (("parametric", model_parametric), ("delaunay", model_delaunay)):
    t0 = time.perf_counter()
    VisualizerImaging.visualize(
        analysis=analysis,
        paths=_paths(name),
        instance=model.instance_from_prior_medians(),
        during_analysis=False,
    )
    print(f"visualize [{name}]: {time.perf_counter() - t0:.1f}s")

n_png = len(list(image_path.rglob("*.png")))
print(f"Wrote {n_png} PNGs under {image_path.relative_to(REPO_ROOT)}")
