"""
Knowledge Graph v4
==================

Database layer for the biomedical knowledge graph used in the
in-silico drug discovery project.

The module stores:

    - biomedical entities,
    - entity mentions,
    - relations,
    - evidence,
    - pharmacological activity values.

It operates on the existing pubmed.db database and does not modify
the articles table.
"""

import sqlite3
from typing import Optional


DATABASE = "pubmed.db"


# ---------------------------------------------------------------------
# Controlled vocabularies
# ---------------------------------------------------------------------

ENTITY_TYPES = {
    "COMPOUND",
    "DRUG",
    "GENE",
    "PROTEIN",
    "DISEASE",
    "TARGET",
    "ASSAY",
}


RELATION_TYPES = {
    "INHIBITS",
    "ACTIVATES",
    "BINDS_TO",
    "TARGETS",
    "TREATS",
    "ASSOCIATED_WITH",
    "REPURPOSED_FOR",
}


ACTIVITY_TYPES = {
    "IC50",
    "EC50",
    "KI",
    "KD",
    "GI50",
    "ED50",
    "MIC",
}


# ---------------------------------------------------------------------
# Database connection
# ---------------------------------------------------------------------

def get_connection():
    """
    Return SQLite connection with foreign-key enforcement enabled.
    """

    connection = sqlite3.connect(DATABASE)

    connection.execute(
        "PRAGMA foreign_keys = ON"
    )

    connection.row_factory = sqlite3.Row

    return connection


# ---------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------

def create_knowledge_graph_tables():
    """
    Create Knowledge Graph v4 tables and indexes.
    """

    connection = get_connection()
    cursor = connection.cursor()

    # -----------------------------------------------------------------
    # Entities
    # -----------------------------------------------------------------

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS kg_entities_v4 (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            canonical_name TEXT NOT NULL,
            entity_type TEXT NOT NULL,

            ontology TEXT,
            concept_id TEXT,

            smiles TEXT,
            inchikey TEXT,

            created_at TIMESTAMP
                DEFAULT CURRENT_TIMESTAMP,

            UNIQUE(
                canonical_name,
                entity_type
            )
        )
        """
    )

    # -----------------------------------------------------------------
    # Mentions
    # -----------------------------------------------------------------

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS kg_mentions_v4 (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            article_id INTEGER NOT NULL,
            entity_id INTEGER NOT NULL,

            surface_form TEXT NOT NULL,

            section TEXT,
            sentence TEXT,

            start_offset INTEGER,
            end_offset INTEGER,

            extraction_method TEXT,
            confidence REAL,

            FOREIGN KEY(article_id)
                REFERENCES articles(id)
                ON DELETE CASCADE,

            FOREIGN KEY(entity_id)
                REFERENCES kg_entities_v4(id)
                ON DELETE CASCADE
        )
        """
    )

    # -----------------------------------------------------------------
    # Relations
    # -----------------------------------------------------------------

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS kg_relations_v4 (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            subject_entity_id INTEGER NOT NULL,
            relation_type TEXT NOT NULL,
            object_entity_id INTEGER NOT NULL,

            confidence REAL,
            extraction_method TEXT,

            created_at TIMESTAMP
                DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY(subject_entity_id)
                REFERENCES kg_entities_v4(id)
                ON DELETE CASCADE,

            FOREIGN KEY(object_entity_id)
                REFERENCES kg_entities_v4(id)
                ON DELETE CASCADE,

            UNIQUE(
                subject_entity_id,
                relation_type,
                object_entity_id
            )
        )
        """
    )

    # -----------------------------------------------------------------
    # Evidence
    # -----------------------------------------------------------------

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS kg_evidence_v4 (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            relation_id INTEGER NOT NULL,
            article_id INTEGER NOT NULL,

            section TEXT,
            sentence TEXT NOT NULL,

            pmid TEXT,
            pmcid TEXT,

            confidence REAL,

            extraction_method TEXT,

            FOREIGN KEY(relation_id)
                REFERENCES kg_relations_v4(id)
                ON DELETE CASCADE,

            FOREIGN KEY(article_id)
                REFERENCES articles(id)
                ON DELETE CASCADE
        )
        """
    )

    # -----------------------------------------------------------------
    # Pharmacological activity
    # -----------------------------------------------------------------

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS kg_activity_v4 (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            relation_id INTEGER NOT NULL,

            activity_type TEXT NOT NULL,

            value REAL,
            unit TEXT,

            comparator TEXT,

            raw_value TEXT,

            FOREIGN KEY(relation_id)
                REFERENCES kg_relations_v4(id)
                ON DELETE CASCADE
        )
        """
    )

    # -----------------------------------------------------------------
    # Indexes
    # -----------------------------------------------------------------

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_kg_entities_v4_name
        ON kg_entities_v4(canonical_name)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_kg_entities_v4_type
        ON kg_entities_v4(entity_type)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_kg_mentions_v4_article
        ON kg_mentions_v4(article_id)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_kg_mentions_v4_entity
        ON kg_mentions_v4(entity_id)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_kg_relations_v4_subject
        ON kg_relations_v4(subject_entity_id)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_kg_relations_v4_object
        ON kg_relations_v4(object_entity_id)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_kg_relations_v4_type
        ON kg_relations_v4(relation_type)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_kg_evidence_v4_article
        ON kg_evidence_v4(article_id)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_kg_evidence_v4_relation
        ON kg_evidence_v4(relation_id)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_kg_activity_v4_relation
        ON kg_activity_v4(relation_id)
        """
    )

    connection.commit()
    connection.close()


# ---------------------------------------------------------------------
# Entity operations
# ---------------------------------------------------------------------

def get_or_create_entity(
    canonical_name: str,
    entity_type: str,
    ontology: Optional[str] = None,
    concept_id: Optional[str] = None,
    smiles: Optional[str] = None,
    inchikey: Optional[str] = None,
):
    """
    Return entity ID.

    If the entity does not exist, create it.
    """

    entity_type = entity_type.upper()

    if entity_type not in ENTITY_TYPES:
        raise ValueError(
            f"Unsupported entity type: {entity_type}"
        )

    canonical_name = canonical_name.strip()

    if not canonical_name:
        raise ValueError(
            "Entity canonical name cannot be empty."
        )

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT id
        FROM kg_entities_v4
        WHERE canonical_name = ?
          AND entity_type = ?
        """,
        (
            canonical_name,
            entity_type,
        ),
    )

    row = cursor.fetchone()

    if row:
        entity_id = row["id"]

        connection.close()

        return entity_id

    cursor.execute(
        """
        INSERT INTO kg_entities_v4 (
            canonical_name,
            entity_type,
            ontology,
            concept_id,
            smiles,
            inchikey
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            canonical_name,
            entity_type,
            ontology,
            concept_id,
            smiles,
            inchikey,
        ),
    )

    entity_id = cursor.lastrowid

    connection.commit()
    connection.close()

    return entity_id


# ---------------------------------------------------------------------
# Mention operations
# ---------------------------------------------------------------------

def add_mention(
    article_id: int,
    entity_id: int,
    surface_form: str,
    section: Optional[str] = None,
    sentence: Optional[str] = None,
    start_offset: Optional[int] = None,
    end_offset: Optional[int] = None,
    extraction_method: Optional[str] = None,
    confidence: Optional[float] = None,
):
    """
    Add an entity mention to an article.
    """

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO kg_mentions_v4 (
            article_id,
            entity_id,
            surface_form,
            section,
            sentence,
            start_offset,
            end_offset,
            extraction_method,
            confidence
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            article_id,
            entity_id,
            surface_form,
            section,
            sentence,
            start_offset,
            end_offset,
            extraction_method,
            confidence,
        ),
    )

    mention_id = cursor.lastrowid

    connection.commit()
    connection.close()

    return mention_id


# ---------------------------------------------------------------------
# Relation operations
# ---------------------------------------------------------------------

def get_or_create_relation(
    subject_entity_id: int,
    relation_type: str,
    object_entity_id: int,
    confidence: Optional[float] = None,
    extraction_method: Optional[str] = None,
):
    """
    Return relation ID.

    Create the relation if it does not already exist.
    """

    relation_type = relation_type.upper()

    if relation_type not in RELATION_TYPES:
        raise ValueError(
            f"Unsupported relation type: {relation_type}"
        )

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT id
        FROM kg_relations_v4
        WHERE subject_entity_id = ?
          AND relation_type = ?
          AND object_entity_id = ?
        """,
        (
            subject_entity_id,
            relation_type,
            object_entity_id,
        ),
    )

    row = cursor.fetchone()

    if row:
        relation_id = row["id"]

        connection.close()

        return relation_id

    cursor.execute(
        """
        INSERT INTO kg_relations_v4 (
            subject_entity_id,
            relation_type,
            object_entity_id,
            confidence,
            extraction_method
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            subject_entity_id,
            relation_type,
            object_entity_id,
            confidence,
            extraction_method,
        ),
    )

    relation_id = cursor.lastrowid

    connection.commit()
    connection.close()

    return relation_id


# ---------------------------------------------------------------------
# Evidence operations
# ---------------------------------------------------------------------

def add_evidence(
    relation_id: int,
    article_id: int,
    sentence: str,
    section: Optional[str] = None,
    pmid: Optional[str] = None,
    pmcid: Optional[str] = None,
    confidence: Optional[float] = None,
    extraction_method: Optional[str] = None,
):
    """
    Add provenance/evidence supporting a relation.
    """

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO kg_evidence_v4 (
            relation_id,
            article_id,
            section,
            sentence,
            pmid,
            pmcid,
            confidence,
            extraction_method
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            relation_id,
            article_id,
            section,
            sentence,
            pmid,
            pmcid,
            confidence,
            extraction_method,
        ),
    )

    evidence_id = cursor.lastrowid

    connection.commit()
    connection.close()

    return evidence_id


# ---------------------------------------------------------------------
# Activity operations
# ---------------------------------------------------------------------

def add_activity(
    relation_id: int,
    activity_type: str,
    value: Optional[float] = None,
    unit: Optional[str] = None,
    comparator: Optional[str] = None,
    raw_value: Optional[str] = None,
):
    """
    Add pharmacological activity associated with a relation.
    """

    activity_type = activity_type.upper()

    if activity_type not in ACTIVITY_TYPES:
        raise ValueError(
            f"Unsupported activity type: {activity_type}"
        )

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO kg_activity_v4 (
            relation_id,
            activity_type,
            value,
            unit,
            comparator,
            raw_value
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            relation_id,
            activity_type,
            value,
            unit,
            comparator,
            raw_value,
        ),
    )

    activity_id = cursor.lastrowid

    connection.commit()
    connection.close()

    return activity_id


# ---------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------

def get_statistics():
    """
    Return basic Knowledge Graph statistics.
    """

    connection = get_connection()
    cursor = connection.cursor()

    tables = {
        "entities": "kg_entities_v4",
        "mentions": "kg_mentions_v4",
        "relations": "kg_relations_v4",
        "evidence": "kg_evidence_v4",
        "activities": "kg_activity_v4",
    }

    statistics = {}

    for name, table in tables.items():

        cursor.execute(
            f"SELECT COUNT(*) FROM {table}"
        )

        statistics[name] = (
            cursor.fetchone()[0]
        )

    connection.close()

    return statistics


def print_statistics():
    """
    Print Knowledge Graph statistics.
    """

    statistics = get_statistics()

    print()
    print("=" * 60)
    print("KNOWLEDGE GRAPH v4")
    print("=" * 60)

    print(
        f"Entities:    "
        f"{statistics['entities']:,}"
    )

    print(
        f"Mentions:    "
        f"{statistics['mentions']:,}"
    )

    print(
        f"Relations:   "
        f"{statistics['relations']:,}"
    )

    print(
        f"Evidence:    "
        f"{statistics['evidence']:,}"
    )

    print(
        f"Activities:  "
        f"{statistics['activities']:,}"
    )

    print("=" * 60)


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------

def main():

    print(
        "Creating Knowledge Graph v4 schema..."
    )

    create_knowledge_graph_tables()

    print(
        "Knowledge Graph v4 schema created successfully."
    )

    print_statistics()


if __name__ == "__main__":
    main()