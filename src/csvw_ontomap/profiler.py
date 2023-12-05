"""CSVW Profile class."""
import glob
import json
import re
from datetime import datetime
from typing import Any, List, Optional

import pandas as pd
from ydata_profiling import ProfileReport

from csvw_ontomap.ontology import load_vectordb, search_vectordb
from csvw_ontomap.utils import BOLD, END, YELLOW, OntomapConfig


class CsvwProfiler:
    def __init__(
        self,
        ontology_url: Optional[str] = None,
        vectordb_path: str = "data/vectordb",
        config: Optional[OntomapConfig] = None,
    ) -> None:
        """Optionally provide an ontology that will be loaded to a vectordb for mapping"""
        self.config = config if config else OntomapConfig()
        self.csvw: Any = CSVW_BASE
        self.ontology_url = ontology_url
        self.vectordb_path = vectordb_path
        if self.ontology_url:
            load_vectordb(self.ontology_url, self.vectordb_path)

    def profile_files(self, files: List[str], config: Optional[OntomapConfig] = None) -> Any:
        """Profile a list of tabular files by generating report using https://github.com/ydataai/ydata-profiling

        If an ontology is provided it will use it to map the files columns to classes/properties of the ontology
        cf. https://www.w3.org/TR/tabular-data-primer/ for CSVW specs
        Search_threshold is between 0 and 1
        """
        config = config if config else self.config
        for glob_file in files:
            file_list = glob.glob(glob_file)

            for file in file_list:
                print(f"🔍 Profiling {BOLD}{YELLOW}{file}{END}")
                # Create new CSVW table for each file
                table: Any = {"url": file, "tableSchema": {"columns": []}}

                # Read file with pandas
                df: pd.DataFrame
                if file.endswith(".xlsx"):
                    df = pd.read_excel(file)
                elif file.endswith(".spss"):
                    df = pd.read_spss(file)
                else:
                    df = pd.read_csv(file, true_values=["true"], false_values=["false"])
                    # TODO: handle when TSV or others
                    # table["dialect"] = {"delimiter": "\t", "headerRowCount": 3}

                # Run ydata profiling to get report
                report = json.loads(ProfileReport(df, title="Profiling Report").to_json())

                # Create a CSVW column for each variable
                for var_name, var_report in report["variables"].items():
                    col = {"titles": var_name, "dc:title": separate_words(var_name)}

                    if self.ontology_url:
                        # Get most matching property or class from the ontology
                        matches = search_vectordb(self.vectordb_path, col["dc:title"], config.comment_best_matches)
                        if matches[0].score >= config.search_threshold:
                            col["propertyUrl"] = matches[0].payload["id"]
                            # col["rdfs:label"] = matches[0].payload["label"]
                            # To use a custom subject URL for this column use (code is the reference to a column title in the same file):
                            # "aboutUrl": "http://example.org/country/{code}#geo",
                        if config.comment_best_matches > 0:
                            col["rdfs:comment"] = "Best matches: " + " - ".join(
                                [
                                    f"[{round(m.score, 2)}] {m.payload['label']} ({m.payload['category']}) <{m.payload['id']}>"
                                    for m in matches
                                ]
                            )
                            # NOTE: not valid to put notes on col
                            # col["notes"] = [
                            #     {
                            #         "score": m.score,
                            #         "id": m.payload["id"],
                            #         "label": m.payload["label"],
                            #         "category": m.payload["category"],
                            #     }
                            #     for m in matches
                            # ]
                            # "notes": [{
                            #     "type": "Annotation",
                            #     "target": "countries.csv#cell=2,6-*,7",
                            #     "body": "These locations are of representative points.",
                            #     "motivation": "commenting"
                            # }]

                    # Available CSVW datatypes: https://github.com/cldf/csvw/blob/master/tests/test_datatypes.py
                    # Integer or float
                    if var_report["type"] == "Numeric":
                        base_type = (
                            "integer" if next(iter(var_report["value_counts_index_sorted"])).isdigit() else "number"
                        )
                        col["datatype"] = {
                            "base": base_type,
                            "minimum": var_report["min"],
                            "maximum": var_report["max"],
                        }
                        # col["constraints"] = {"minimum": var_report["min"], "maximum": var_report["max"]}
                        # TODO: add mean? median?
                        # Add format to details the 0 displayed? https://www.w3.org/TR/tabular-data-primer/#number-precision
                        # TODO: Add unit information? https://www.w3.org/TR/tabular-data-primer/#uom-datatypes
                        # "datatype": {
                        #     "@id": "http://example.org/unit/kilometre",
                        #     "@type": "http://example.org/quantity/length",
                        #     "rdfs:label": "Kilometre",
                        #     "base": "number",
                        #     "skos:notation": "km"
                        # }

                    # Category
                    elif var_report["type"] == "Categorical":
                        # base_type = (
                        #     "integer" if next(iter(var_report["value_counts_index_sorted"])).isdigit() else "string"
                        # )
                        col["datatype"] = {
                            "base": "string",
                            "format": "|".join(list(var_report["value_counts_index_sorted"].keys())),
                        }

                    # Boolean
                    elif var_report["type"] == "Boolean":
                        col["datatype"] = {"base": "boolean", "format": "|".join(df[var_name].unique())}
                    else:
                        col["datatype"] = "string"

                    # col["null"] = "NA" // Indicates "NA" is used for missing values in this column

                    table["tableSchema"]["columns"].append(col)

                # NOTE: we could also add types to the tables: https://www.w3.org/TR/tabular-data-primer/#row-types
                # Try to use the VectorDB to infer the table type based on all columns? Or use LLM
                # table_type = "schema:Country"
                # table["tableSchema"]["columns"].append({
                #     "virtual": True,
                #     "propertyUrl": "rdf:type",
                #     "valueUrl": table_type
                # })

                # NOTE: possible to add transformations scripts: https://www.w3.org/TR/tabular-data-primer/#extension-transformations
                # table["transformations"] = [{
                #     "targetFormat": "http://www.iana.org/assignments/media-types/application/xml",
                #     "titles": "Simple XML version",
                #     "url": "xml-template.mustache",
                #     "scriptFormat": "https://mustache.github.io/",
                #     "source": "json"
                # }]

                self.csvw["tables"].append(table)
        self.csvw["dc:created"] = {"@value": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"), "@type": "xsd:dateTime"}
        return self.csvw


def separate_words(input_string: str) -> str:
    """Separate words in column labels (e.g. RestingECG becomes Resting ECG)"""
    # Replace underscores with spaces for snake_case
    input_string = input_string.replace("_", " ")
    # Insert spaces before capital letters for CamelCase
    return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", input_string)


CSVW_BASE = {
    "@context": ["http://www.w3.org/ns/csvw", {"@language": "en"}],
    # "dc:title": "CSVW profiling report",
    "dialect": {"header": True, "encoding": "utf-8"},
    "tables": [],
}
