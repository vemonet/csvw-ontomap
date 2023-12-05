<div align="center">

# 🔎 CSVW OntoMap 🗺️

[![PyPI - Version](https://img.shields.io/pypi/v/csvw-ontomap.svg?logo=pypi&label=PyPI&logoColor=silver)](https://pypi.org/project/csvw-ontomap/)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/csvw-ontomap.svg?logo=python&label=Python&logoColor=silver)](https://pypi.org/project/csvw-ontomap/)
[![license](https://img.shields.io/pypi/l/csvw-ontomap.svg?color=%2334D058)](https://github.com/vemonet/csvw-ontomap/blob/main/LICENSE.txt)

[![Test package](https://github.com/vemonet/csvw-ontomap/actions/workflows/test.yml/badge.svg)](https://github.com/vemonet/csvw-ontomap/actions/workflows/test.yml)
[![Publish package](https://github.com/vemonet/csvw-ontomap/actions/workflows/publish.yml/badge.svg)](https://github.com/vemonet/csvw-ontomap/actions/workflows/publish.yml)

[![Hatch project](https://img.shields.io/badge/%F0%9F%A5%9A-Hatch-4051b5.svg)](https://github.com/pypa/hatch) [![linting - Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/charliermarsh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff) [![code style - Black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black) [![types - Mypy](https://img.shields.io/badge/types-Mypy-blue.svg)](https://github.com/python/mypy)

</div>

Automatically generate descriptive [CSVW](https://csvw.org) (CSV on the Web) metadata for tabular data files:

- **Extract columns datatypes**: detect if they are categorical, and which values are accepted.
- **Ontology mappings**: when provided with a URL to an OWL ontology, text embeddings are generated and stored in a local Qdrant vector database for all classes and properties, we use similarity search to match each data column to the most relevant ontology terms.
- Currently supports: CSV, Excel, SPSS files. Any format that can be loaded in a Pandas DataFrame could be easily added, create an issue on GitHub to request a new format to be added.

> [!WARNING]
>
> Processed files needs to contain 1 sheet, if multiple sheets are present in a file only the first one will be processed.

## 📦️ Installation

This package requires Python >=3.8, simply install it with:

```bash
pip install git+https://github.com/vemonet/csvw-ontomap.git
```

## 🪄 Usage

### ⌨️ Use as a command-line interface

You can easily use your package from your terminal after installing `csvw-ontomap` with pip:

```bash
csvw-ontomap tests/resources/*.csv
```

Store CSVW metadata report output to file:

```bash
csvw-ontomap tests/resources/*.csv -o csvw-report.json
```

Provide the URL to an OWL ontology that will be used to map the column names:

```bash
csvw-ontomap tests/resources/*.csv -m https://semanticscience.org/ontology/sio.owl
```

Specify the path to store the vectors (default is `data/vectordb`):

```bash
csvw-ontomap tests/resources/*.csv -m https://semanticscience.org/ontology/sio.owl -d data/vectordb
```

### 🐍 Use with python

Use this package in python scripts:

```python
from csvw_ontomap import CsvwProfiler, OntomapConfig
import json

profiler = CsvwProfiler(
    ontology_url="https://semanticscience.org/ontology/sio.owl",
    vectordb_path="data/vectordb",
    config=OntomapConfig(       # Optional
        comment_best_matches=3, # Add the ontology matches as comment
        search_threshold=0,     # Between 0 and 1
    ),
)
csvw_report = profiler.profile_files([
    "tests/resources/*.csv",
    "tests/resources/*.xlsx",
    "tests/resources/*.spss",
])
print(json.dumps(csvw_report, indent=2))
```

## 🧑‍💻 Development setup

The final section of the README is for if you want to run the package in development, and get involved by making a code contribution.


### 📥️ Clone

Clone the repository:

```bash
git clone https://github.com/vemonet/csvw-ontomap
cd csvw-ontomap
```

### 🐣 Install dependencies

Install [Hatch](https://hatch.pypa.io), this will automatically handle virtual environments and make sure all dependencies are installed when you run a script in the project:

```bash
pipx install hatch
```

### ☑️ Run tests

Make sure the existing tests still work by running the test suite and linting checks. Note that any pull requests to the fairworkflows repository on github will automatically trigger running of the test suite;

```bash
hatch run test
```

To display all logs when debugging:

```bash
hatch run test -s
```


### ♻️ Reset the environment

In case you are facing issues with dependencies not updating properly you can easily reset the virtual environment with:

```bash
hatch env prune
```

Manually trigger installing the dependencies in a local virtual environment:

```bash
hatch -v env create
```

### 🏷️ New release process

The deployment of new releases is done automatically by a GitHub Action workflow when a new release is created on GitHub. To release a new version:

1. Make sure the `PYPI_TOKEN` secret has been defined in the GitHub repository (in Settings > Secrets > Actions). You can get an API token from PyPI at [pypi.org/manage/account](https://pypi.org/manage/account).
2. Increment the `version` number in the `pyproject.toml` file in the root folder of the repository.

    ```bash
    hatch version fix
    ```

3. Create a new release on GitHub, which will automatically trigger the publish workflow, and publish the new release to PyPI.

You can also do it locally:

```bash
hatch build
hatch publish
```
