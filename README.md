# radial-intensity-analysis
A snakemake workflow for performing radial intensity analysis of signal in the nucleolus

## Quick Overview

### Input files

Place raw TIFF stacks here:

```
data/
```

### Run

```bash
snakemake -j 8 --use-conda --conda-frontend conda 
```

Outputs land in `results/<experiment>/`.


## Installation

1. **Install Miniconda or Conda** (e.g. [Miniconda](https://docs.conda.io/en/latest/miniconda.html)).

2. Install git on the computer if not present

3. **Install the environment using the yml file**:

   ```bash
   conda env create -f workflow/environment.yml
   ```

Note:** If you encounter issues with java or sql. Check out out Troubleshooting section.

4. **Clone this repository** and move into it:

   ```bash
   git clone <repo-url>
   cd <repo>
   ```


## Deeper Dive

### Folder structure

```
├── data/                # raw input TIFF stacks
│   ├─── <experiment1>/
│   │    └── <sample>.tif
│   ├── <experiment2>/
│   │    └── <sample>.tif
├── resources/           # static assets (CellProfiler .cppipe, plugins)
│   ├── rdf.cppipe
│   └── plugins/
├── workflow/            # workflow code & envs
│   ├── Snakefile
│   ├── scripts/
│   │   ├── mip.py
│   │   └── rdf.py
│   └── envs/
│       └── environment.yaml
├── results/             # generated outputs
│   └── <experiment>/
│       ├── mip/
│       ├── cellprofiler_outputs/
│       └── plots/
└── logs/                # runtime logs (auto‑generated)
```

### How to tweak the workflow

| What you want to change   | Where / how                                                                        |
| ------------------------- | ---------------------------------------------------------------------------------- |
| **MIP channels & LUT**    | Edit `channels` / `colors` parameters in rule **mip** inside `Snakefile`           |
| **CellProfiler pipeline** | Replace `resources/rdf.cppipe` and adjust `pipeline` path in rule **cellprofiler** |

---

If you run into issues or have improvements, feel free to open an issue or pull request.
