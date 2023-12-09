"""Load and search an ontology with a vectordb."""
from typing import Any, Iterable, List

from fastembed.embedding import FlagEmbedding as Embedding
from qdrant_client import QdrantClient
from qdrant_client.http.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchText,
    PointStruct,
    VectorParams,
)
from rdflib import Graph

from csvw_ontomap.utils import BOLD, CYAN, END

EMBEDDING_MODEL_NAME = "BAAI/bge-base-en"
EMBEDDING_MODEL_SIZE = 768

COLLECTION_NAME = "csvw-ontomap"


def load_vectordb(ontologies: List[str], vectordb_path: str, recreate: bool = False) -> None:
    # Initialize FastEmbed and Qdrant Client
    print("📥 Loading embedding model")
    embedding_model = Embedding(model_name=EMBEDDING_MODEL_NAME, max_length=512)
    vectordb = QdrantClient(path=vectordb_path)

    try:
        print(f"Total vectors in DB: {vectordb.get_collection(COLLECTION_NAME).points_count}")
    except:
        recreate = True

    if recreate:
        print(f"🔄 Recreating VectorDB in {vectordb_path}")
        vectordb.recreate_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=EMBEDDING_MODEL_SIZE, distance=Distance.COSINE),
        )

    for ontology_url in ontologies:
        print(f"\n📚 Loading ontology from {BOLD}{CYAN}{ontology_url}{END}")

        # NOTE: We use oxrdflib to handle large ontologies (600M+)
        g = Graph(store="Oxigraph")
        try:
            g.parse(ontology_url)
        except Exception as e:
            print(f"Default parsing failed, trying with XML parser: {e}")
            g.parse(ontology_url, format="xml")

        # For each ontology check if there are more vectors than classes/properties, and skip building if enough vectors for this ontology
        onto_vector_count = get_onto_vectors_count(vectordb, ontology_url)
        q_count_cls = """PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
        PREFIX rdfs:  <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX owl:  <http://www.w3.org/2002/07/owl#>
        SELECT (COUNT(DISTINCT ?uri) as ?clsCount)
        WHERE {
            ?uri a ?type .
            FILTER (
                ?type = owl:Class ||
                ?type = owl:DatatypeProperty ||
                ?type = owl:ObjectProperty
            )
        }
        """
        all_onto_count = 0
        results: Iterable[Any] = g.query(q_count_cls)
        for res in results:
            all_onto_count = int(res.clsCount)
            break
        print(
            f"{BOLD}{all_onto_count}{END} classes/properties in the ontology | {BOLD}{onto_vector_count}{END} loaded in the VectorDB"
        )
        if onto_vector_count > all_onto_count:
            print("⏩ Skip loading")
            continue

        # Get classes labels
        q_cls_labels = """PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
        PREFIX rdfs:  <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX owl:  <http://www.w3.org/2002/07/owl#>
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        PREFIX dc: <http://purl.org/dc/elements/1.1/>
        PREFIX dcterms: <http://purl.org/dc/terms/>

        SELECT ?uri ?pred ?label ?type
        WHERE {
            ?uri a ?type ;
                ?pred ?label .
            FILTER (
                ?type = owl:Class
            )
            FILTER (
                ?pred = rdfs:label ||
                ?pred = skos:prefLabel ||
                ?pred = skos:altLabel ||
                ?pred = skos:definition ||
                ?pred = rdfs:comment ||
                ?pred = dcterms:description ||
                ?pred = dc:title
            )
        }
        """
        embed_labels(g.query(q_cls_labels), "classes", ontology_url, vectordb, embedding_model)

        # Get properties labels (separated to classes to reduce the size of the queries for big ontologies)
        q_prop_labels = """PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
        PREFIX rdfs:  <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX owl:  <http://www.w3.org/2002/07/owl#>
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        PREFIX dc: <http://purl.org/dc/elements/1.1/>
        PREFIX dcterms: <http://purl.org/dc/terms/>

        SELECT ?uri ?pred ?label ?type
        WHERE {
            ?uri a ?type ;
                ?pred ?label .
            FILTER (
                ?type = owl:DatatypeProperty ||
                ?type = owl:ObjectProperty
            )
            FILTER (
                ?pred = rdfs:label ||
                ?pred = skos:prefLabel ||
                ?pred = skos:altLabel ||
                ?pred = skos:definition ||
                ?pred = rdfs:comment ||
                ?pred = dcterms:description ||
                ?pred = dc:title
            )
        }
        """
        embed_labels(g.query(q_prop_labels), "properties", ontology_url, vectordb, embedding_model)


def get_onto_vectors_count(vectordb: Any, ontology: str) -> int:
    """Get vector count for a specific ontology URL"""
    search_result = vectordb.scroll(
        collection_name=COLLECTION_NAME,
        scroll_filter=Filter(should=[FieldCondition(key="ontology", match=MatchText(text=ontology))]),
        limit=99999999,
    )
    return len(list(search_result[0]))


def embed_labels(concepts_labels: Any, category: str, ontology_url: str, vectordb: Any, embedding_model: Any) -> None:
    """Generate and upload embeddings for labels extracted from an ontology"""
    concept_labels = []
    concept_uris = []
    concept_payloads = []
    # Prepare list of labels to be embedded
    for cl in concepts_labels:
        concept_labels.append(str(cl.label))
        concept_uris.append(str(cl.uri))
        concept_payloads.append(
            {
                "pred": str(cl.pred),
                "type": str(cl.type),
            }
        )
    concepts_count = len(set(concept_uris))
    print(f"⏳ Generating {len(concept_uris)} embeddings for {concepts_count} {category}")

    # Generate embeddings, and upload them
    embeddings = list(embedding_model.embed(concept_labels))
    points_count: int = vectordb.get_collection(COLLECTION_NAME).points_count
    class_points = [
        PointStruct(
            id=points_count + i,
            vector=embedding,
            payload={
                "id": uri,
                "label": label,
                "type": payload["type"],
                "ontology": ontology_url,
                "predicate": payload["pred"],
            },
        )
        for i, (uri, label, payload, embedding) in enumerate(
            zip(concept_uris, concept_labels, concept_payloads, embeddings)
        )
    ]
    # print(f"{BOLD}{len(class_points)}{END} vectors generated for {concepts_count} {category}")
    vectordb.upsert(collection_name=COLLECTION_NAME, points=class_points)


def search_vectordb(vectordb_path: str, search_query: str, limit: int = 3) -> Any:  # -> Any:
    """Search matching entities in the vectordb"""
    if limit <= 0:
        limit = 3
    # Initialize FastEmbed and Qdrant Client
    embedding_model = Embedding(model_name=EMBEDDING_MODEL_NAME, max_length=512)
    vectordb = QdrantClient(path=vectordb_path)

    query_embeddings = list(embedding_model.embed([search_query]))

    return vectordb.search(
        collection_name=COLLECTION_NAME,
        query_vector=query_embeddings[0],
        limit=limit,
    )
    # for hit in hits: print(hit.payload, "score:", hit.score)
