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
2. **Install the nevironemnt using the yml file**:

   ```bash
   conda install -f workflow/environment.yml
   ```
3. **Clone this repository** and move into it:

   ```bash
   git clone <repo-url>
   cd <repo>
   ```


## Deeper Dive

### Folder structure

```
├── data/                # raw input TIFF stacks
│   └── <experiment>/
│       └── <sample>.tif
├── resources/           # static assets (CellProfiler .cppipe, plugins)
│   ├── rdf.cppipe
│   └── plugins/
├── workflow/            # workflow code & envs
│   ├── Snakefile
│   ├── scripts/
│   │   ├── mip.py
│   │   └── rdf.py
│   └── envs/
│       ├── ds.yaml
│       └── cellprofiler.yaml
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
