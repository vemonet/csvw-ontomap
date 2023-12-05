"""Generate CSVW (CSV on the Web) metadata for CSV file.

Automatically extract columns datatypes, if they are categorical, which values are accepted.
Map to ontology concepts if OWL ontology provided"""

__version__ = "0.0.1"

from .utils import OntomapConfig
from .profiler import CsvwProfiler
