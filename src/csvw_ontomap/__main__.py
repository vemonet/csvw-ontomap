import json
from typing import List

import typer

from csvw_ontomap.profiler import CsvwProfiler
from csvw_ontomap.utils import BOLD, CYAN, END, OntomapConfig

cli = typer.Typer()


@cli.command("profile")
def cli_profile(
    files: List[str] = typer.Argument(None, help="Files to profile"),
    ontology: str = typer.Option(None, "-m", help="URL to the OWL ontology to map the CSV columns to"),
    vectordb: str = typer.Option("data/vectordb", "-d", help="Path to the VectorDB"),
    best_matches: int = typer.Option(0, help="Number of best matches to add to each column as rdfs:comment"),
    threshold: float = typer.Option(
        0, help="Do not add propertyUrl if the match score is under this threshold, between 0 and 1"
    ),
    output: str = typer.Option(None, "-o", help="Path to save the generated CSVW JSON metadata"),
    verbose: bool = typer.Option(True, help="Display logs"),
) -> None:
    config = OntomapConfig(
        comment_best_matches=best_matches,
        search_threshold=threshold,
    )
    profiler = CsvwProfiler(ontology, vectordb, config)
    report = profiler.profile_files(files)
    if output:
        if verbose:
            print(f"Writing to file {BOLD}{CYAN}{output}{END}")
        with open(output, "w") as file:
            file.write(json.dumps(report, indent=2))
    else:
        print(json.dumps(report, indent=2))


# @cli.command("version")
# def cli_version() -> None:
#     print(__version__)


if __name__ == "__main__":
    cli()
