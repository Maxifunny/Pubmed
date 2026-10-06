import sqlite3
import re
from collections import Counter

import spacy


# ============================================================
# CONFIGURATION
# ============================================================

DATABASE = "pubmed.db"
MODEL = "en_core_sci_sm"

MIN_ENTITY_LENGTH = 3
MIN_ENTITY_FREQUENCY = 2


# ============================================================
# LOAD NLP MODEL
# ============================================================

print("Loading SciSpaCy model...")

nlp = spacy.load(MODEL)

# Scientific articles can be long.
nlp.max_length = 3_000_000


# ============================================================
# DATABASE STRUCTURE
# ============================================================

def create_knowledge_graph_tables(connection):

    cursor = connection.cursor()

    # --------------------------------------------------------
    # ENTITIES
    # --------------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS entities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            normalized_name TEXT NOT NULL UNIQUE,
            entity_type TEXT,
            total_mentions INTEGER DEFAULT 0
        )
    """)

    # --------------------------------------------------------
    # ARTICLE <-> ENTITY
    # --------------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS article_entities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            article_id INTEGER NOT NULL,
            entity_id INTEGER NOT NULL,

            mention_count INTEGER DEFAULT 1,

            FOREIGN KEY(article_id)
                REFERENCES articles(id),

            FOREIGN KEY(entity_id)
                REFERENCES entities(id),

            UNIQUE(article_id, entity_id)
        )
    """)

    # --------------------------------------------------------
    # RELATIONS
    #
    # We create the table now, but do not populate it yet.
    # --------------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS relations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            article_id INTEGER NOT NULL,

            source_entity_id INTEGER NOT NULL,
            target_entity_id INTEGER NOT NULL,

            relation_type TEXT NOT NULL,

            evidence_sentence TEXT,
            section TEXT,

            confidence REAL,

            FOREIGN KEY(article_id)
                REFERENCES articles(id),

            FOREIGN KEY(source_entity_id)
                REFERENCES entities(id),

            FOREIGN KEY(target_entity_id)
                REFERENCES entities(id)
        )
    """)

    connection.commit()


# ============================================================
# ENTITY NORMALIZATION
# ============================================================

def normalize_entity(text):

    text = text.strip()

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    text = text.strip(
        ".,;:()[]{}"
    )

    return text


def canonical_entity(text):

    normalized = normalize_entity(text)

    return normalized.lower()


# ============================================================
# LOAD ARTICLES FROM SQLITE
# ============================================================

def load_articles(connection):

    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            id,
            pmid,
            pmcid,
            title,
            full_text
        FROM articles
        WHERE full_text IS NOT NULL
          AND length(full_text) > 0
    """)

    rows = cursor.fetchall()

    articles = []

    for row in rows:

        articles.append({
            "id": row[0],
            "pmid": row[1],
            "pmcid": row[2],
            "title": row[3],
            "full_text": row[4],
        })

    return articles


# ============================================================
# ENTITY EXTRACTION
# ============================================================

def extract_entities(text):

    doc = nlp(text)

    entities = []

    for entity in doc.ents:

        name = normalize_entity(
            entity.text
        )

        if len(name) < MIN_ENTITY_LENGTH:
            continue

        # Ignore entities consisting only of numbers.
        if name.isdigit():
            continue

        entities.append(name)

    return entities


# ============================================================
# INSERT / UPDATE ENTITY
# ============================================================

def get_or_create_entity(
    connection,
    entity_name
):

    cursor = connection.cursor()

    normalized_name = canonical_entity(
        entity_name
    )

    cursor.execute("""
        SELECT id
        FROM entities
        WHERE normalized_name = ?
    """, (
        normalized_name,
    ))

    result = cursor.fetchone()

    if result:

        return result[0]

    cursor.execute("""
        INSERT INTO entities (
            name,
            normalized_name,
            entity_type,
            total_mentions
        )
        VALUES (?, ?, ?, 0)
    """, (
        entity_name,
        normalized_name,
        "BIOMEDICAL_ENTITY",
    ))

    return cursor.lastrowid


# ============================================================
# SAVE ARTICLE-ENTITY ASSOCIATION
# ============================================================

def save_article_entity(
    connection,
    article_id,
    entity_id,
    mention_count
):

    cursor = connection.cursor()

    cursor.execute("""
        INSERT INTO article_entities (
            article_id,
            entity_id,
            mention_count
        )
        VALUES (?, ?, ?)

        ON CONFLICT(article_id, entity_id)
        DO UPDATE SET
            mention_count =
                excluded.mention_count
    """, (
        article_id,
        entity_id,
        mention_count,
    ))


# ============================================================
# PROCESS ARTICLE
# ============================================================

def process_article(
    connection,
    article
):

    print()
    print("=" * 70)

    print(
        f"PMID:  {article['pmid']}"
    )

    print(
        f"PMCID: {article['pmcid']}"
    )

    print(
        f"Title: {article['title']}"
    )

    print()

    entities = extract_entities(
        article["full_text"]
    )

    counts = Counter(
        canonical_entity(entity)
        for entity in entities
    )

    display_names = {}

    for entity in entities:

        normalized = canonical_entity(
            entity
        )

        if normalized not in display_names:

            display_names[
                normalized
            ] = entity

    saved = 0

    for normalized_name, count in counts.items():

        if count < MIN_ENTITY_FREQUENCY:
            continue

        entity_name = display_names[
            normalized_name
        ]

        entity_id = get_or_create_entity(
            connection,
            entity_name
        )

        save_article_entity(
            connection,
            article["id"],
            entity_id,
            count
        )

        saved += 1

    connection.commit()

    print(
        f"Detected mentions: {len(entities)}"
    )

    print(
        f"Unique entities:   {len(counts)}"
    )

    print(
        f"Saved entities:    {saved}"
    )


# ============================================================
# UPDATE GLOBAL ENTITY COUNTS
# ============================================================

def update_entity_statistics(
    connection
):

    cursor = connection.cursor()

    cursor.execute("""
        UPDATE entities
        SET total_mentions = COALESCE(
            (
                SELECT SUM(
                    article_entities.mention_count
                )
                FROM article_entities
                WHERE article_entities.entity_id =
                      entities.id
            ),
            0
        )
    """)

    connection.commit()


# ============================================================
# STATISTICS
# ============================================================

def print_statistics(
    connection
):

    cursor = connection.cursor()

    print()
    print("=" * 70)
    print("KNOWLEDGE GRAPH DATABASE")
    print("=" * 70)

    cursor.execute("""
        SELECT COUNT(*)
        FROM entities
    """)

    entity_count = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*)
        FROM article_entities
    """)

    association_count = (
        cursor.fetchone()[0]
    )

    cursor.execute("""
        SELECT COUNT(DISTINCT article_id)
        FROM article_entities
    """)

    article_count = (
        cursor.fetchone()[0]
    )

    print()
    print(
        f"Processed articles: {article_count}"
    )

    print(
        f"Entities:           {entity_count}"
    )

    print(
        f"Article-entity links: "
        f"{association_count}"
    )

    print()

    print("Most frequently mentioned entities:")
    print()

    cursor.execute("""
        SELECT
            name,
            total_mentions
        FROM entities
        ORDER BY total_mentions DESC
        LIMIT 30
    """)

    for name, mentions in cursor.fetchall():

        print(
            f"{mentions:6}  {name}"
        )


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 70)
    print("Biomedical Knowledge Graph Builder")
    print("=" * 70)
    print()

    connection = sqlite3.connect(
        DATABASE
    )

    # Enforce SQLite foreign keys.
    connection.execute(
        "PRAGMA foreign_keys = ON"
    )

    create_knowledge_graph_tables(
        connection
    )

    articles = load_articles(
        connection
    )

    print(
        f"Found {len(articles)} "
        f"articles with full text."
    )

    for article in articles:

        process_article(
            connection,
            article
        )

    update_entity_statistics(
        connection
    )

    print_statistics(
        connection
    )

    connection.close()

    print()
    print("Finished.")
    print()


if __name__ == "__main__":
    main()