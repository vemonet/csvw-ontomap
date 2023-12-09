"""Load and search an ontology with a vectordb."""
from typing import Any, List

from fastembed.embedding import FlagEmbedding as Embedding
from owlready2 import get_ontology
from qdrant_client import QdrantClient
from qdrant_client.http.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchText,
    PointStruct,
    VectorParams,
)

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
        print(f"Vectors in DB: {vectordb.get_collection(COLLECTION_NAME).points_count}")
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

        onto = get_ontology(ontology_url).load()
        # For each ontology check if there are more vectors than classes/properties, and skip building if enough vectors for this ontology
        all_onto_count = len(list(onto.classes())) + len(list(onto.properties()))
        onto_vector_count = get_vectors_count(vectordb, ontology_url)
        print(
            f"{all_onto_count} classes/properties in the ontology | {BOLD}{onto_vector_count}{END} loaded in the VectorDB"
        )
        if onto_vector_count > all_onto_count:
            print("⏩ Skip loading")
            continue

        # Find labels, generate embeddings, and upload them using owlready2
        upload_concepts(onto.classes(), "class", ontology_url, vectordb, embedding_model)
        upload_concepts(onto.properties(), "property", ontology_url, vectordb, embedding_model)

        # NOTE: Try to use oxrdflib to handle large ontologies (600M+)
        # g = Graph(store="Oxigraph")
        # g.parse(ontology_url)
        # q = """
        # PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
        # PREFIX rdfs:  <http://www.w3.org/2000/01/rdf-schema#>
        # PREFIX owl:  <http://www.w3.org/2002/07/owl#>
        # PREFIX skos: <http://www.w3.org/2004/02/skos/core#>

        # SELECT *
        # WHERE {
        #     ?class a owl:Class ;
        #         rdfs:label/skos:prefLabel ?label .
        # }
        # """
        # for r in g.query(q):
        #     print(r)


def get_vectors_count(vectordb: Any, ontology: str) -> int:
    search_result = vectordb.scroll(
        collection_name=COLLECTION_NAME,
        scroll_filter=Filter(should=[FieldCondition(key="ontology", match=MatchText(text=ontology))]),
        # with_vectors=True,
        # with_payload=True,
        limit=999999,
    )
    return len(list(search_result[0]))


def upload_concepts(onto_concepts: Any, category: str, ontology_url: str, vectordb: Any, embedding_model: Any) -> None:
    """Generate and upload embeddings for label and description of a list of owlready2 classes/properties"""
    # concepts_count = len(list(onto_concepts))
    concepts_count = 0
    concept_labels = []
    concept_uris = []
    for concept in onto_concepts:
        # print(f"Class URI: {ent.iri}, Label: {ent.label}, Description: {str(ent.description.first())}, Comment: {ent.comment}")
        # print(concept.label, concept.comment, concept.name)
        if concept.label:
            concept_uris.append(concept.iri)
            concept_labels.append(str(concept.label.first()))
        try:
            if concept.description:
                concept_uris.append(concept.iri)
                concept_labels.append(str(concept.description[0]))
        except:
            pass
        # try:
        if concept.comment:
            # print("COMMENT", concept.comment[0])
            concept_uris.append(concept.iri)
            concept_labels.append(str(concept.comment[0]))
        # except:
        #     pass
        concepts_count += 1
    print(f"⏳ Generating {len(concept_uris)} embeddings for {concepts_count} {category}")

    # Generate embeddings, and upload them
    embeddings = list(embedding_model.embed(concept_labels))
    points_count: int = vectordb.get_collection(COLLECTION_NAME).points_count
    class_points = [
        PointStruct(
            id=points_count + i,
            vector=embedding,
            payload={"id": uri, "label": label, "category": category, "ontology": ontology_url},
        )
        for i, (uri, label, embedding) in enumerate(zip(concept_uris, concept_labels, embeddings))
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
