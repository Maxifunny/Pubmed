"""
Knowledge Graph v4.1
====================

Biomedical knowledge graph database layer for the
in-silico drug discovery project.

Main design principle:

ENTITY -> RELATION -> ASSERTION -> ACTIVITY

A relation represents a general semantic relationship, e.g.:

    Compound X --INHIBITS--> PDE4

An assertion represents evidence for that relationship
in a specific article/context.

An assertion may contain one or more quantitative
activity measurements, e.g.:

    IC50 = 12 nM
    Ki   = 8 nM
"""

import sqlite3
from typing import Optional


DATABASE = "pubmed.db"


# ============================================================
# Controlled vocabularies
# ============================================================

ENTITY_TYPES = {
    "COMPOUND",
    "DRUG",
    "GENE",
    "PROTEIN",
    "DISEASE",
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


EVIDENCE_TYPES = {
    "COMPUTATIONAL",
    "IN_VITRO",
    "IN_VIVO",
    "CLINICAL",
    "REVIEW",
    "OTHER",
}


# ============================================================
# Database connection
# ============================================================

def get_connection():

    connection = sqlite3.connect(DATABASE)

    connection.execute(
        "PRAGMA foreign_keys = ON"
    )

    connection.row_factory = sqlite3.Row

    return connection


# ============================================================
# Schema
# ============================================================

def create_knowledge_graph_tables():

    connection = get_connection()
    cursor = connection.cursor()

    # --------------------------------------------------------
    # ENTITIES
    # --------------------------------------------------------

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS kg_entities_v41 (

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

    # --------------------------------------------------------
    # ENTITY MENTIONS
    # --------------------------------------------------------

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS kg_mentions_v41 (

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
                REFERENCES kg_entities_v41(id)
                ON DELETE CASCADE
        )
        """
    )

    # --------------------------------------------------------
    # RELATIONS
    #
    # General semantic relationship:
    #
    # compound --INHIBITS--> protein
    # --------------------------------------------------------

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS kg_relations_v41 (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            subject_entity_id INTEGER NOT NULL,

            relation_type TEXT NOT NULL,

            object_entity_id INTEGER NOT NULL,

            created_at TIMESTAMP
                DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY(subject_entity_id)
                REFERENCES kg_entities_v41(id)
                ON DELETE CASCADE,

            FOREIGN KEY(object_entity_id)
                REFERENCES kg_entities_v41(id)
                ON DELETE CASCADE,

            UNIQUE(
                subject_entity_id,
                relation_type,
                object_entity_id
            )
        )
        """
    )

    # --------------------------------------------------------
    # ASSERTIONS
    #
    # Evidence for a relation in a particular article.
    # --------------------------------------------------------

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS kg_assertions_v41 (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            relation_id INTEGER NOT NULL,
            article_id INTEGER NOT NULL,

            section TEXT,

            evidence_sentence TEXT NOT NULL,

            evidence_type TEXT,

            assay TEXT,

            extraction_method TEXT,
            confidence REAL,

            created_at TIMESTAMP
                DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY(relation_id)
                REFERENCES kg_relations_v41(id)
                ON DELETE CASCADE,

            FOREIGN KEY(article_id)
                REFERENCES articles(id)
                ON DELETE CASCADE
        )
        """
    )

    # --------------------------------------------------------
    # ACTIVITY MEASUREMENTS
    #
    # Activity belongs to an assertion, NOT directly
    # to a global relation.
    # --------------------------------------------------------

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS kg_activity_v41 (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            assertion_id INTEGER NOT NULL,

            activity_type TEXT NOT NULL,

            value REAL,

            unit TEXT,

            comparator TEXT,

            raw_value TEXT,

            FOREIGN KEY(assertion_id)
                REFERENCES kg_assertions_v41(id)
                ON DELETE CASCADE
        )
        """
    )

    # ========================================================
    # Indexes
    # ========================================================

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_entities_v41_name
        ON kg_entities_v41(canonical_name)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_entities_v41_type
        ON kg_entities_v41(entity_type)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_mentions_v41_article
        ON kg_mentions_v41(article_id)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_mentions_v41_entity
        ON kg_mentions_v41(entity_id)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_relations_v41_subject
        ON kg_relations_v41(subject_entity_id)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_relations_v41_object
        ON kg_relations_v41(object_entity_id)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_relations_v41_type
        ON kg_relations_v41(relation_type)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_assertions_v41_relation
        ON kg_assertions_v41(relation_id)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_assertions_v41_article
        ON kg_assertions_v41(article_id)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_activity_v41_assertion
        ON kg_activity_v41(assertion_id)
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_activity_v41_type
        ON kg_activity_v41(activity_type)
        """
    )

    connection.commit()
    connection.close()


# ============================================================
# ENTITY OPERATIONS
# ============================================================

def get_or_create_entity(
    canonical_name: str,
    entity_type: str,
    ontology: Optional[str] = None,
    concept_id: Optional[str] = None,
    smiles: Optional[str] = None,
    inchikey: Optional[str] = None,
):

    entity_type = entity_type.upper()

    if entity_type not in ENTITY_TYPES:

        raise ValueError(
            f"Unsupported entity type: {entity_type}"
        )

    canonical_name = canonical_name.strip()

    if not canonical_name:

        raise ValueError(
            "Entity name cannot be empty."
        )

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT id
        FROM kg_entities_v41
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
        INSERT INTO kg_entities_v41 (
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


# ============================================================
# MENTION OPERATIONS
# ============================================================

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

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO kg_mentions_v41 (
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


# ============================================================
# RELATION OPERATIONS
# ============================================================

def get_or_create_relation(
    subject_entity_id: int,
    relation_type: str,
    object_entity_id: int,
):

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
        FROM kg_relations_v41
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
        INSERT INTO kg_relations_v41 (
            subject_entity_id,
            relation_type,
            object_entity_id
        )
        VALUES (?, ?, ?)
        """,
        (
            subject_entity_id,
            relation_type,
            object_entity_id,
        ),
    )

    relation_id = cursor.lastrowid

    connection.commit()
    connection.close()

    return relation_id


# ============================================================
# ASSERTION OPERATIONS
# ============================================================

def add_assertion(
    relation_id: int,
    article_id: int,
    evidence_sentence: str,
    section: Optional[str] = None,
    evidence_type: Optional[str] = None,
    assay: Optional[str] = None,
    extraction_method: Optional[str] = None,
    confidence: Optional[float] = None,
):

    if evidence_type:

        evidence_type = evidence_type.upper()

        if evidence_type not in EVIDENCE_TYPES:

            raise ValueError(
                f"Unsupported evidence type: "
                f"{evidence_type}"
            )

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO kg_assertions_v41 (
            relation_id,
            article_id,
            section,
            evidence_sentence,
            evidence_type,
            assay,
            extraction_method,
            confidence
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            relation_id,
            article_id,
            section,
            evidence_sentence,
            evidence_type,
            assay,
            extraction_method,
            confidence,
        ),
    )

    assertion_id = cursor.lastrowid

    connection.commit()
    connection.close()

    return assertion_id


# ============================================================
# ACTIVITY OPERATIONS
# ============================================================

def add_activity(
    assertion_id: int,
    activity_type: str,
    value: Optional[float] = None,
    unit: Optional[str] = None,
    comparator: Optional[str] = None,
    raw_value: Optional[str] = None,
):

    activity_type = activity_type.upper()

    if activity_type not in ACTIVITY_TYPES:

        raise ValueError(
            f"Unsupported activity type: "
            f"{activity_type}"
        )

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO kg_activity_v41 (
            assertion_id,
            activity_type,
            value,
            unit,
            comparator,
            raw_value
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            assertion_id,
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


# ============================================================
# Statistics
# ============================================================

def get_statistics():

    connection = get_connection()
    cursor = connection.cursor()

    tables = {
        "entities": "kg_entities_v41",
        "mentions": "kg_mentions_v41",
        "relations": "kg_relations_v41",
        "assertions": "kg_assertions_v41",
        "activities": "kg_activity_v41",
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

    stats = get_statistics()

    print()
    print("=" * 60)
    print("KNOWLEDGE GRAPH v4.1")
    print("=" * 60)

    print(
        f"Entities:    {stats['entities']:,}"
    )

    print(
        f"Mentions:    {stats['mentions']:,}"
    )

    print(
        f"Relations:   {stats['relations']:,}"
    )

    print(
        f"Assertions:  {stats['assertions']:,}"
    )

    print(
        f"Activities:  {stats['activities']:,}"
    )

    print("=" * 60)


# ============================================================
# Main
# ============================================================

def main():

    print(
        "Creating Knowledge Graph v4.1 schema..."
    )

    create_knowledge_graph_tables()

    print(
        "Knowledge Graph v4.1 schema "
        "created successfully."
    )

    print_statistics()


if __name__ == "__main__":
    main()