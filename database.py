import sqlite3


DATABASE = "pubmed.db"


# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_connection():
    """
    Create a connection to the SQLite database.
    Foreign-key support is enabled for every connection.
    """
    connection = sqlite3.connect(DATABASE)
    connection.execute("PRAGMA foreign_keys = ON")

    return connection


# ============================================================
# DATABASE INITIALIZATION
# ============================================================

def create_database():
    """
    Create all required database tables.

    Existing tables and data are preserved.
    """
    connection = get_connection()
    cursor = connection.cursor()

    # --------------------------------------------------------
    # ARTICLES
    # --------------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pmid TEXT UNIQUE NOT NULL,
            pmcid TEXT,
            doi TEXT,
            title TEXT,
            authors TEXT,
            journal TEXT,
            publication_year TEXT,
            abstract TEXT,
            full_text TEXT,
            license TEXT,
            downloaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # --------------------------------------------------------
    # SEARCH HISTORY
    # --------------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS searches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query TEXT NOT NULL,
            start_year INTEGER,
            end_year INTEGER,
            pmc_only INTEGER DEFAULT 0,
            pubmed_total INTEGER DEFAULT 0,
            requested INTEGER DEFAULT 0,
            retrieved INTEGER DEFAULT 0,
            full_text_downloaded INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # --------------------------------------------------------
    # DOWNLOAD FAILURES
    # --------------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS download_failures (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pmid TEXT NOT NULL,
            pmcid TEXT,
            stage TEXT NOT NULL,
            error_message TEXT,
            attempt_count INTEGER DEFAULT 1,
            last_attempt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            UNIQUE(pmid, stage)
        )
    """)

    connection.commit()
    connection.close()


# ============================================================
# ARTICLES
# ============================================================

def save_article(article):
    """
    Insert a PubMed article into the database.

    If the PMID already exists, update its metadata without
    overwriting an existing PMCID with NULL.
    """

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        INSERT INTO articles (
            pmid,
            pmcid,
            doi,
            title,
            authors,
            journal,
            publication_year,
            abstract
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)

        ON CONFLICT(pmid) DO UPDATE SET

            pmcid = COALESCE(
                excluded.pmcid,
                articles.pmcid
            ),

            doi = excluded.doi,
            title = excluded.title,
            authors = excluded.authors,
            journal = excluded.journal,
            publication_year = excluded.publication_year,
            abstract = excluded.abstract
    """, (
        article["pmid"],
        article.get("pmcid"),
        article.get("doi"),
        article.get("title"),
        article.get("authors"),
        article.get("journal"),
        article.get("year"),
        article.get("abstract"),
    ))

    connection.commit()
    connection.close()


def update_full_text(
    pmid,
    pmcid,
    full_text,
):
    """
    Store the full article text and PMCID.
    """

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        UPDATE articles

        SET
            pmcid = ?,
            full_text = ?,
            downloaded_at = CURRENT_TIMESTAMP

        WHERE pmid = ?
    """, (
        pmcid,
        full_text,
        pmid,
    ))

    connection.commit()
    connection.close()


def has_full_text(pmid):
    """
    Check whether a full-text article is already stored.
    """

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT 1

        FROM articles

        WHERE pmid = ?

          AND full_text IS NOT NULL

          AND length(full_text) > 0

        LIMIT 1
    """, (pmid,))

    result = cursor.fetchone()

    connection.close()

    return result is not None


def get_article_by_pmid(pmid):
    """
    Retrieve an article using its PMID.
    """

    connection = get_connection()

    connection.row_factory = sqlite3.Row

    cursor = connection.cursor()

    cursor.execute("""
        SELECT *
        FROM articles
        WHERE pmid = ?
        LIMIT 1
    """, (pmid,))

    result = cursor.fetchone()

    connection.close()

    if result is None:
        return None

    return dict(result)


# ============================================================
# SEARCH HISTORY
# ============================================================

def create_search(
    query,
    start_year,
    end_year,
    pmc_only,
    pubmed_total,
    requested,
):
    """
    Register a new PubMed search.
    """

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        INSERT INTO searches (
            query,
            start_year,
            end_year,
            pmc_only,
            pubmed_total,
            requested
        )

        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        query,
        start_year,
        end_year,
        int(pmc_only),
        pubmed_total,
        requested,
    ))

    search_id = cursor.lastrowid

    connection.commit()
    connection.close()

    return search_id


def update_search(
    search_id,
    retrieved,
    full_text_downloaded,
):
    """
    Update corpus-building statistics.
    """

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        UPDATE searches

        SET
            retrieved = ?,
            full_text_downloaded = ?

        WHERE id = ?
    """, (
        retrieved,
        full_text_downloaded,
        search_id,
    ))

    connection.commit()
    connection.close()


# ============================================================
# DOWNLOAD FAILURE LOG
# ============================================================

def log_download_failure(
    pmid,
    pmcid,
    stage,
    error_message,
):
    """
    Register a failed download.

    Repeated failures for the same PMID and stage increment
    attempt_count instead of creating duplicate records.
    """

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        INSERT INTO download_failures (
            pmid,
            pmcid,
            stage,
            error_message,
            attempt_count,
            last_attempt
        )

        VALUES (
            ?,
            ?,
            ?,
            ?,
            1,
            CURRENT_TIMESTAMP
        )

        ON CONFLICT(pmid, stage) DO UPDATE SET

            pmcid = excluded.pmcid,

            error_message =
                excluded.error_message,

            attempt_count =
                download_failures.attempt_count + 1,

            last_attempt =
                CURRENT_TIMESTAMP
    """, (
        pmid,
        pmcid,
        stage,
        str(error_message),
    ))

    connection.commit()
    connection.close()


def clear_download_failure(pmid):
    """
    Remove failure records after a successful download.
    """

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        DELETE FROM download_failures
        WHERE pmid = ?
    """, (pmid,))

    connection.commit()
    connection.close()


def get_download_failures():
    """
    Return all unresolved download failures.
    """

    connection = get_connection()

    connection.row_factory = sqlite3.Row

    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            pmid,
            pmcid,
            stage,
            error_message,
            attempt_count,
            last_attempt

        FROM download_failures

        ORDER BY
            last_attempt DESC
    """)

    rows = cursor.fetchall()

    connection.close()

    return [
        dict(row)
        for row in rows
    ]


# ============================================================
# DATABASE STATISTICS
# ============================================================

def get_database_statistics():
    """
    Return basic corpus statistics.
    """

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT

            COUNT(*) AS total_articles,

            SUM(
                CASE
                    WHEN pmcid IS NOT NULL
                    THEN 1
                    ELSE 0
                END
            ) AS pmc_articles,

            SUM(
                CASE
                    WHEN full_text IS NOT NULL
                         AND length(full_text) > 0
                    THEN 1
                    ELSE 0
                END
            ) AS full_text_articles

        FROM articles
    """)

    row = cursor.fetchone()

    connection.close()

    return {
        "total_articles": row[0] or 0,
        "pmc_articles": row[1] or 0,
        "full_text_articles": row[2] or 0,
    }


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    create_database()

    statistics = get_database_statistics()

    print()
    print("=" * 60)
    print("DATABASE INITIALIZED")
    print("=" * 60)

    print(
        f"Total articles:     "
        f"{statistics['total_articles']}"
    )

    print(
        f"PMC articles:       "
        f"{statistics['pmc_articles']}"
    )

    print(
        f"Full-text articles: "
        f"{statistics['full_text_articles']}"
    )

    print("=" * 60)