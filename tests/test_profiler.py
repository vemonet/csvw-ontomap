import json
from typing import Any

from csvw import CSVW

from csvw_ontomap import CsvwProfiler, OntomapConfig, __version__

ONTOLOGIES = [
    # "https://semanticscience.org/ontology/sio.owl",
    # "http://www.lesfleursdunormal.fr/static/_downloads/omop_cdm_v6.owl",
    "data/LOINC.ttl",
]


def test_profiler():
    """Test the Profiler without ontology"""
    profiler = CsvwProfiler()
    csvw_report = profiler.profile_files(["tests/resources/heart.csv"])
    validate_csvw(csvw_report)


def test_profiler_with_ontology():
    """Test the Profiler with ontology"""
    profiler = CsvwProfiler(ONTOLOGIES)
    csvw_report = profiler.profile_files(["tests/resources/heart.csv"])
    validate_csvw(csvw_report)


def test_profiler_with_ontology_best_matches():
    """Test the Profiler with ontology and add best matches"""
    profiler = CsvwProfiler(ONTOLOGIES, config=OntomapConfig(comment_best_matches=3))
    csvw_report = profiler.profile_files(["tests/resources/heart.csv"])
    validate_csvw(csvw_report)


def test_version():
    """Test the version is a string."""
    assert isinstance(__version__, str)


def validate_csvw(csvw_report: Any):
    print(json.dumps(csvw_report, indent=2))
    tmp_file = "./tmp-metadata.json"
    with open(tmp_file, "w") as file:
        json.dump(csvw_report, file, indent=2)
    csvw = CSVW(tmp_file, validate=True)
    if csvw.is_valid:
        print("CSVW OK")
    else:
        print("FAIL")
        for w in csvw.warnings:
            print(str(w.message))
        raise Exception("CSVW not valid")
