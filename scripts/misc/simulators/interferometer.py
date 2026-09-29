"""
Simulator: Instrument-Based Interferometer Datasets
===================================================

Simulates a single-galaxy interferometer dataset for one of the
``instruments.interferometer.INSTRUMENTS`` presets (``sma`` / ``alma`` /
``alma_high`` / ``jvla``) and writes ``data.fits``, ``noise_map.fits``,
``uv_wavelengths.fits`` and ``galaxies.json`` into
``dataset/interferometer/<instrument>/``.

Adapted from ``autolens_visualization/scripts/misc/simulators/interferometer.py``
(itself the simulator half of ``autolens_profiling``'s) for a single-plane
PyAutoGalaxy dataset: the uv-coverage, transformer and simulator settings are
unchanged; the model is the SAME galaxy as ``scripts/misc/simulators/imaging.py``
(``Sersic`` bulge + ``Exponential`` disk), so the imaging and interferometer
galleries show one galaxy. One deliberate change: the visibilities are transformed
from the preset's circular real-space mask (the one the producer fits with), not the
full grid, because the disk extends past the 3.5" mask.

The tracked ``dataset/interferometer/sma/`` was produced by::

    python scripts/misc/simulators/interferometer.py --instrument sma

Usage
-----

    python scripts/misc/simulators/interferometer.py                  # sma (default)
    python scripts/misc/simulators/interferometer.py --instrument alma
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

from instruments.interferometer import INSTRUMENTS  # noqa: E402

_REPO_ROOT = _repo_root()


def simulate(instrument: str = "sma", output_root: Path | None = None) -> Path:
    """Simulate the named interferometer instrument. Returns the dataset directory."""
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
    real_space_shape = config["real_space_shape"]
    n_visibilities = config["n_visibilities"]
    uv_scale = config["uv_scale"]
    noise_sigma = config["noise_sigma"]
    seed = config["seed"]
    transformer_choice = config.get("transformer", "dft").lower()
    transformer_chunk_size = config.get("transformer_chunk_size", None)
    if transformer_choice == "nufft":

        def transformer_class(uv_wavelengths, real_space_mask):
            return ag.TransformerNUFFT(
                uv_wavelengths=uv_wavelengths,
                real_space_mask=real_space_mask,
                chunk_size=transformer_chunk_size,
            )
    elif transformer_choice == "dft":
        transformer_class = ag.TransformerDFT
    else:
        raise ValueError(f"Unknown transformer '{transformer_choice}'")

    root = output_root if output_root is not None else _REPO_ROOT
    dataset_path = root / "dataset" / "interferometer" / instrument
    dataset_path.mkdir(parents=True, exist_ok=True)

    print(f"\n--- Interferometer simulator [{instrument}] ---")
    print(f"  pixel_scale:      {pixel_scale} arcsec/px")
    print(f"  real_space_shape: {real_space_shape[0]} x {real_space_shape[1]}")
    print(f"  n_visibilities:   {n_visibilities:,}")
    print(f"  output:           {dataset_path}")

    # The visibilities are transformed from
    # the SAME circular real-space mask the producer fits with: the Exponential disk
    # extends past ``mask_radius``, so simulating on the full grid would put flux in the
    # data that the masked true model cannot reproduce (a spurious residual in every
    # fit panel). The lens repo's compact source never hit this.
    real_space_mask = ag.Mask2D.circular(
        shape_native=real_space_shape,
        pixel_scales=pixel_scale,
        radius=config["mask_radius"],
    )
    # over_sample_size=1: the Interferometer dataset the producer loads evaluates light
    # profiles without over-sampling, so a sub-sampled simulation of the cuspy n=3 bulge
    # would leave a central residual in the true-model fit.
    grid = ag.Grid2D.from_mask(mask=real_space_mask, over_sample_size=1)

    # Synthetic baselines drawn from a 2D isotropic Gaussian whose 3-sigma envelope
    # matches ``uv_scale``. Seeded for reproducibility.
    rng = np.random.default_rng(seed)
    uv_wavelengths = rng.normal(loc=0.0, scale=uv_scale / 3.0, size=(n_visibilities, 2)).astype(
        np.float64
    )

    simulator = ag.SimulatorInterferometer(
        uv_wavelengths=uv_wavelengths,
        exposure_time=300.0,
        noise_sigma=noise_sigma,
        transformer_class=transformer_class,
        noise_seed=seed,
    )

    # Same galaxy as scripts/misc/simulators/imaging.py.
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

    aplt.fits_interferometer(
        dataset=dataset,
        data_path=dataset_path / "data.fits",
        noise_map_path=dataset_path / "noise_map.fits",
        uv_wavelengths_path=dataset_path / "uv_wavelengths.fits",
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
        default="sma",
        choices=list(INSTRUMENTS.keys()),
        help="Instrument preset to simulate (default: sma).",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=None,
        help="Override the repo root that holds dataset/ (default: inferred from this file).",
    )
    args = parser.parse_args()
    simulate(instrument=args.instrument, output_root=args.output_root)
