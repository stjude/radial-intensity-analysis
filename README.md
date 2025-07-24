# radial-intensity-analysis
A snakemake workflow for performing radial intensity analysis of signal in the nucleolus

## Quick Overview

### Input files

Place raw experiment folders with TIFF stacks here:

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

2. Install [git](https://git-scm.com/book/en/v2/Getting-Started-Installing-Git) on the computer if not present

    If you are in Windows skip to the [Troubleshooting](#troubleshooting) section instead of step 3.

3. **Install the environment using the yml file**:

   ```bash
   conda env create -f workflow/environment.yml
   ```

    **Note:** If you encounter issues with java or sql. Check out out [Troubleshooting](#troubleshooting) section.

4. **Clone this repository** and move into it:

   ```bash
   git clone <repo-url>
   cd <repo>
   ```


## Deeper Dive

### Folder structure

```
├── data/                # raw input TIF/TIFF stacks
│   ├── <experiment1>/
│   │   ├── <sample1>.tif
│   │   └── <sample2>.tif
│   └── <experiment2>/
│       └── <sample1>.tiff
├── resources/           # static assets (CellProfiler .cppipe, plugins)
│   ├── rdf.cppipe
│   └── plugins/
├── workflow/            # workflow code & envs
│   ├── Snakefile
│   ├── scripts/
│   │   ├── mip.py
│   │   └── rdf.py
│   ├── envs/
│   │   └── environment.yaml
│   └── logs/            # runtime logs (auto‑generated)
└── results/             # generated outputs
    └── <experiment>/
        ├── mip/
        ├── cellprofiler_outputs/
        └── plots/

```

### How to tweak the workflow

| What you want to change   | Where / how                                                                        |
| ------------------------- | ---------------------------------------------------------------------------------- |
| **MIP channels & LUT**    | Edit `channels` / `colors` parameters in rule **mip** inside `Snakefile`           |
| **CellProfiler pipeline** | Replace `resources/rdf.cppipe` and adjust `pipeline` path in rule **cellprofiler** |

---

If you run into issues or have improvements, feel free to open an issue or pull request.

## Troubleshooting

### Windows Pre-installations

These instructions are for installing CellProfiler 4.0+, and < 5, which will run on Python 3. To install the previous 3.1.9 release, see this [page](https://github.com/CellProfiler/CellProfiler/wiki/Source-installation-(Windows)/e208c4f38cad30d21a3062a5dcf74788811aa39c).
 
#### Downloading CellProfiler's libraries and dependencies
 
Download and install packages for [Python 3.8](http://www.python.org/downloads/windows) 64-bit on your machine  

We recommend starting with a fresh install of Python (in a conda environment).

When installing, it's a good idea to enable the "Add python to path" option

#### Download and install [Microsoft Visual C++ Redistributable 2015-2022](https://docs.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist?view=msvc-170)

Select the version appropriate for your architecture. On windows, you can determine this by going to Control Panel then searching for System and looking next to "System type:" for your processor architecture.
#### Download and install [Microsoft Visual Studio C++ build tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/)

NOTE: Make sure to check 'Desktop development with C++' under Desktop and Mobile in the installer

Also make sure the following packages are installed ( Go inside Visual Studio's "Modify" option to check):
* .NET Framework 4.8 development tools (targeting pack and SDK)
* C++ CMake tools for Windows
* MSVC v143 - VS 2022 C++ x64/x86 build tools (choose the latest)
* MSVC v140 - VS 2015 C++ x64/x86 build tools (choose the latest)
* SQL Server Data Tools - Build Tools
* C++ core features
* C++ Build Tools core features
* MSBuid support for LLVM (clang-cl) toolset
* Windows 11 SDK (if on Windows 11) els Windows 10 SDK - highest version number
* Window Universal C Runtime

#### Download and install [Java JDK 11](https://adoptopenjdk.net/) (The OpenJDK distribution is now called Temurin)
Click on the default installation icon on the website, It will install the appropriate one for your system.

You can alternatively install from [oracle.com](https://www.oracle.com/java/technologies/javase-jdk11-downloads.html) if you'd like, though you will need to make an Oracle account.

Access the [Windows Environment Variables](https://docs.oracle.com/en/database/oracle/machine-learning/oml4r/1.5.1/oread/creating-and-modifying-environment-variables-on-windows.html#GUID-DD6F9982-60D5-48F6-8270-A27EC53807D0) and make sure that both JAVA_HOME and JDK_HOME are set to the location of your JDK installation (one or both may be set during the installation process, depending on the exact installer you used and your configuration during install).
For each new variable, set its value to the location of your JDK installation (i.e., the location of the folder beginning with 'jdk11'). You can do this by clicking the Browse Directory... button. Usually this is in your 'Program Files' in a folder called 'Java'.

#### Open Command Prompt

``cd`` into the directory where you cloned CellProfiler

Type ``pip install -e .``
 
Type ``conda install -c bioconda -c conda-forge snakemake``
If you run into errors, especially any with cellprofiler_core in the stack trace, you may want to also clone and install CellProfiler-core from source; if you do this, you will typically need to also pull core whenever pulling your CellProfiler master.

 ```bash
$ git clone https://github.com/CellProfiler/core.git
$ cd core 
$ git switch 4.2.x
$ pip3 install -e .
```
 
If you encounter any other errors, please get in touch (with the cellprofiler team)!
 
#### Starting CellProfiler
At this point, CellProfiler is installed! You may now run CellProfiler by typing cellprofiler from the command line
 
Change the directory of plugins to the github downloaded plugin folder

``File > Preferences > Plugin``