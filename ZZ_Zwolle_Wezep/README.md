# Standalone Lengkeek L2024-R2010 GEF classifier

This version is for running directly in VS Code or a normal terminal. It does **not** require VIKTOR.

## What to run

Run `main.py`.

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py sample_gef.GEF
```

On macOS/Linux, activate with:

```bash
source .venv/bin/activate
```

## Run with your own GEF file

Put your `.GEF` file in this folder and run:

```bash
python main.py your_file.GEF
```

Optionally override the water level:

```bash
python main.py your_file.GEF --water-level -1.23
```

Disable the optional Bqt/Isbt pore-pressure filter:

```bash
python main.py your_file.GEF --no-bqt
```

## Outputs

The script writes results to the `output` folder:

- `classified_points.csv`: classification for every CPT measurement point.
- `interpreted_layers.csv`: merged soil layers.
- `cpt_lengkeek_profile.png`: qc, Rf and classified profile.
- `lengkeek_r2010_chart.png`: Rf vs qt/pa chart with Lengkeek boundaries.

## Model implemented

The code is already set to Lengkeek **L2024-R2010** conditions:

- Peat: `aorg = 16.7`, `borg = 0.25`, `Rf,min = 5.1`.
- Organic clay: `aorg = 10.3`, `borg = 0.15`, `Rf,min = 2.7`.
- Optional Bqt/Isbt boundaries from equations 9-11 are applied when `u2` and water level are available.

The non-organic classes are a coarse Robertson-style fallback. The main purpose of this standalone version is the Lengkeek organic-soils classification.
