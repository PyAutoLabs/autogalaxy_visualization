"""
Simulator: Instrument-Based Imaging Datasets
============================================

Simulates a single-galaxy imaging dataset for one of the
``instruments.imaging.INSTRUMENTS`` presets (``euclid`` / ``hst`` / ``jwst`` /
``jwst_lw`` / ``ao``) and writes ``data.fits``, ``psf.fits``, ``noise_map.fits`` and
``galaxies.json`` into ``dataset/imaging/<instrument>/``.

Adapted from ``autolens_visualization/scripts/misc/simulators/imaging.py`` (itself the
simulator half of ``autolens_profiling``'s) for a single-plane PyAutoGalaxy dataset:
the grid, over-sampling, PSF and simulator settings are unchanged; the model is one
galaxy (no mass, no second plane), the galaxy of
``autogalaxy_workspace_test/scripts/imaging/jax_likelihood/simulator.py`` at HST-scale
resolution.

The tracked ``dataset/imaging/hst/`` was produced by::

    python scripts/misc/simulators/imaging.py --instrument hst

The true model (restated verbatim by ``scripts/imaging/visualization.py`` and used by
``scripts/ellipse/visualization.py``'s dataset):

- galaxy (z=0.5): ``Sersic`` bulge + ``Exponential`` disk, both centred on (0, 0).

Usage
-----

    python scripts/misc/simulators/imaging.py                       # hst (default)
    python scripts/misc/simulators/imaging.py --instrument euclid
"""

import sys as _sys
from pathlib import Path as _Path


def _repo_root() -> _Path:
    for _p in _Path(__file__).resolve().parents:
        if (_p / "ruff.toml").exists():
            return _p
    raise RuntimeError("autogalaxy_visualization root (ruff.toml) not found")


for _extra in (_repo_root(), _repo_root() / "scripts" / "misc"):
    if str(_extra) not in _sys.path:
        _sys.path.insert(0, str(_extra))

from pathlib import Path

from instruments.imaging import INSTRUMENTS  # noqa: E402

_REPO_ROOT = _repo_root()


def simulate(instrument: str = "hst", output_root: Path | None = None) -> Path:
    """Simulate the named imaging instrument. Returns the dataset dir."""
    import matplotlib
    import numpy as np

    matplotlib.use("Agg")
    import autogalaxy as ag
    import autogalaxy.plot as aplt

    if instrument not in INSTRUMENTS:
        raise ValueError(
            f"Unknown instrument '{instrument}'. Choose from: {list(INSTRUMENTS.keys())}"
        )

    config = INSTRUMENTS[instrument]
    pixel_scale = config["pixel_scale"]
    mask_radius = config["mask_radius"]
    psf_shape = config["psf_shape"]
    psf_sigma = config["psf_sigma"]
    seed = config["seed"]

    root = output_root if output_root is not None else _REPO_ROOT
    dataset_path = root / "dataset" / "imaging" / instrument
    dataset_path.mkdir(parents=True, exist_ok=True)

    # Grid size derived so the mask_radius circular mask fits in the image.
    shape_pixels = int(np.ceil(2 * mask_radius / pixel_scale))
    if shape_pixels % 2 == 0:
        shape_pixels += 1  # odd for symmetric centering

    print(f"\n--- Imaging simulator [{instrument}] ---")
    print(f"  pixel_scale: {pixel_scale} arcsec/px")
    print(f"  grid_shape:  {shape_pixels} x {shape_pixels}")
    print(f"  output:      {dataset_path}")

    grid = ag.Grid2D.uniform(shape_native=(shape_pixels, shape_pixels), pixel_scales=pixel_scale)
    over_sample_size = ag.util.over_sample.over_sample_size_via_radial_bins_from(
        grid=grid,
        sub_size_list=[32, 8, 2],
        radial_list=[0.3, 0.6],
        centre_list=[(0.0, 0.0)],
    )
    grid = grid.apply_over_sampling(over_sample_size=over_sample_size)

    psf = ag.Convolver.from_gaussian(
        shape_native=psf_shape,
        sigma=psf_sigma,
        pixel_scales=grid.pixel_scales,
    )
    simulator = ag.SimulatorImaging(
        exposure_time=300.0,
        psf=psf,
        background_sky_level=0.1,
        add_poisson_noise_to_data=True,
        noise_seed=seed,
    )

    galaxy = ag.Galaxy(
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

    galaxies = ag.Galaxies(galaxies=[galaxy])

    dataset = simulator.via_galaxies_from(galaxies=galaxies, grid=grid)

    aplt.fits_imaging(
        dataset=dataset,
        data_path=dataset_path / "data.fits",
        psf_path=dataset_path / "psf.fits",
        noise_map_path=dataset_path / "noise_map.fits",
        overwrite=True,
    )

    ag.output_to_json(obj=galaxies, file_path=dataset_path / "galaxies.json")

    print(f"  wrote {dataset_path}")
    return dataset_path


if __name__ == "__main__":
    import argparse

    from autonerves import jax_wrapper  # noqa: F401

    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--instrument",
        type=str,
        default="hst",
        choices=list(INSTRUMENTS.keys()),
        help="Instrument preset to simulate (default: hst).",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=None,
        help="Override the repo root that holds dataset/ (default: inferred from this file).",
    )
    args = parser.parse_args()
    simulate(instrument=args.instrument, output_root=args.output_root)
