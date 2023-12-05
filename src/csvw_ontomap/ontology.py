"""Load and search an ontology with a vectordb."""
from typing import Any

from fastembed.embedding import FlagEmbedding as Embedding
from owlready2 import get_ontology
from qdrant_client import QdrantClient
from qdrant_client.http.models import (
    Distance,
    PointStruct,
    VectorParams,
)

from csvw_ontomap.utils import BOLD, CYAN, END

EMBEDDING_MODEL_NAME = "BAAI/bge-base-en"
EMBEDDING_MODEL_SIZE = 768

COLLECTION_NAME = "csvw-ontomap"


def load_vectordb(ontology_url: str, vectordb_path: str) -> None:
    print(f"📚 Loading ontology from {BOLD}{CYAN}{ontology_url}{END}")
    onto = get_ontology(ontology_url).load()

    # Initialize FastEmbed and Qdrant Client
    print("📥 Loading embedding model")
    embedding_model = Embedding(model_name=EMBEDDING_MODEL_NAME, max_length=512)

    vectordb = QdrantClient(path=vectordb_path)

    # Check if vectordb is already loaded
    try:
        all_onto_count = len(list(onto.classes())) + len(list(onto.properties()))
        vectors_count = vectordb.get_collection(COLLECTION_NAME).points_count
        print(
            f"{all_onto_count} classes/properties in the ontology. And currently {BOLD}{vectors_count}{END} loaded in the VectorDB"
        )
        if vectors_count <= all_onto_count:
            raise Exception("Not enough vectors.")
    except Exception as e:
        print(f"🔄 {e!s} Recreating VectorDB")
        vectordb.recreate_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=EMBEDDING_MODEL_SIZE, distance=Distance.COSINE),
        )

        # Find labels, generate embeddings, and upload them
        upload_concepts(onto.classes(), "class", vectordb, embedding_model)
        upload_concepts(onto.properties(), "property", vectordb, embedding_model)


def upload_concepts(onto_concepts: Any, category: str, vectordb: Any, embedding_model: Any) -> None:
    """Generate and upload embeddings for label and description of a list of owlready2 classes/properties"""
    print(f"🌀 Generating embeddings for {CYAN}{category}{END}")  # ⏳
    concept_labels = []
    concept_uris = []
    for concept in onto_concepts:
        # print(f"Class URI: {ent.iri}, Label: {ent.label}, Description: {str(ent.description.first())}, Comment: {ent.comment}")
        if concept.label:
            concept_uris.append(concept.iri)
            concept_labels.append(str(concept.label.first()))
        if concept.description:
            concept_uris.append(concept.iri)
            concept_labels.append(str(concept.description.first()))

    # Generate embeddings, and upload them
    embeddings = list(embedding_model.embed(concept_labels))
    points_count: int = vectordb.get_collection(COLLECTION_NAME).points_count
    class_points = [
        PointStruct(id=points_count + i, vector=embedding, payload={"id": uri, "label": label, "category": category})
        for i, (uri, label, embedding) in enumerate(zip(concept_uris, concept_labels, embeddings))
    ]
    print(f"{BOLD}{len(class_points)}{END} vectors generated for {len(list(onto_concepts))} {category}")
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
