import sqlite3
import time

from database import (
    update_full_text,
    clear_download_failure,
)

from pmc import (
    download_bioc_xml,
    bioc_xml_to_text,
    save_pmc_article,
)


DATABASE = "pubmed.db"

# Conservative delay between BioC requests.
REQUEST_DELAY = 1.0


def get_failed_articles():
    """
    Return failed articles that still do not have full text.

    Only records with a PMCID are considered.
    """

    connection = sqlite3.connect(DATABASE)

    connection.row_factory = sqlite3.Row

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT DISTINCT
            a.pmid,
            a.pmcid,
            a.title,
            df.stage,
            df.error_message
        FROM download_failures AS df
        JOIN articles AS a
            ON a.pmid = df.pmid
        WHERE
            (a.full_text IS NULL OR TRIM(a.full_text) = '')
            AND a.pmcid IS NOT NULL
            AND TRIM(a.pmcid) != ''
        ORDER BY a.pmid
        """
    )

    rows = cursor.fetchall()

    connection.close()

    return rows


def update_failure(pmid, error_message):
    """
    Update the failure information without deleting the record.
    """

    connection = sqlite3.connect(DATABASE)

    cursor = connection.cursor()

    cursor.execute(
        """
        UPDATE download_failures
        SET
            error_message = ?,
            attempt_count = attempt_count + 1,
            last_attempt = CURRENT_TIMESTAMP
        WHERE pmid = ?
        """,
        (
            error_message,
            pmid,
        )
    )

    connection.commit()

    connection.close()


def retry_article(article):
    """
    Try to recover one article directly through BioC.

    OAI is intentionally not called because these records
    have already failed during the original corpus build.
    """

    pmid = article["pmid"]
    pmcid = article["pmcid"]

    print()
    print("-" * 70)

    print(
        f"PMID:  {pmid}"
    )

    print(
        f"PMCID: {pmcid}"
    )

    if article["title"]:
        print(
            f"Title: {article['title']}"
        )

    print(
        "Trying BioC recovery..."
    )

    try:

        # ----------------------------------------------------
        # DOWNLOAD BioC XML
        # ----------------------------------------------------

        bioc_xml = download_bioc_xml(
            pmcid
        )

        # ----------------------------------------------------
        # CONVERT TO TEXT
        # ----------------------------------------------------

        full_text = bioc_xml_to_text(
            bioc_xml
        )

        if not full_text.strip():

            raise ValueError(
                "BioC produced empty full text."
            )

        # ----------------------------------------------------
        # SAVE LOCAL FILES
        # ----------------------------------------------------

        save_pmc_article(
            pmid=pmid,
            pmcid=pmcid,
            xml_content=bioc_xml,
            full_text=full_text,
            source="bioc"
        )

        # ----------------------------------------------------
        # UPDATE DATABASE
        # ----------------------------------------------------

        update_full_text(
            pmid,
            pmcid,
            full_text
        )

        # ----------------------------------------------------
        # REMOVE FAILURE RECORD
        # ----------------------------------------------------

        clear_download_failure(
            pmid
        )

        print(
            "RECOVERED successfully using BioC."
        )

        print(
            f"Text length: "
            f"{len(full_text):,} characters"
        )

        return True

    except Exception as error:

        error_message = (
            "BioC recovery failed: "
            f"{error}"
        )

        print(
            error_message
        )

        update_failure(
            pmid,
            error_message
        )

        return False


def print_database_statistics():
    """
    Print current database statistics after recovery.
    """

    connection = sqlite3.connect(
        DATABASE
    )

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM articles
        """
    )

    total_articles = (
        cursor.fetchone()[0]
    )

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM articles
        WHERE pmcid IS NOT NULL
          AND TRIM(pmcid) != ''
        """
    )

    with_pmcid = (
        cursor.fetchone()[0]
    )

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM articles
        WHERE full_text IS NOT NULL
          AND TRIM(full_text) != ''
        """
    )

    with_full_text = (
        cursor.fetchone()[0]
    )

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM download_failures
        """
    )

    failures = (
        cursor.fetchone()[0]
    )

    connection.close()

    print()
    print("-" * 70)

    print(
        "DATABASE AFTER RECOVERY"
    )

    print("-" * 70)

    print(
        f"Total articles:          "
        f"{total_articles:,}"
    )

    print(
        f"Articles with PMCID:     "
        f"{with_pmcid:,}"
    )

    print(
        f"Articles with full text: "
        f"{with_full_text:,}"
    )

    print(
        f"Remaining failures:      "
        f"{failures:,}"
    )


def main():

    print(
        "=" * 70
    )

    print(
        "PMC BioC FAILURE RECOVERY"
    )

    print(
        "=" * 70
    )

    failed_articles = (
        get_failed_articles()
    )

    total = len(
        failed_articles
    )

    print(
        f"Articles eligible for recovery: "
        f"{total}"
    )

    if total == 0:

        print(
            "Nothing to recover."
        )

        return

    recovered = 0
    failed = 0

    for index, article in enumerate(
        failed_articles,
        start=1
    ):

        print()
        print(
            "=" * 70
        )

        print(
            f"[{index}/{total}]"
        )

        success = retry_article(
            article
        )

        if success:
            recovered += 1

        else:
            failed += 1

        # Avoid unnecessary delay after the last article.
        if index < total:

            time.sleep(
                REQUEST_DELAY
            )

    print()
    print(
        "=" * 70
    )

    print(
        "RECOVERY COMPLETED"
    )

    print(
        "=" * 70
    )

    print(
        f"Articles processed:      "
        f"{total}"
    )

    print(
        f"Recovered using BioC:    "
        f"{recovered}"
    )

    print(
        f"Still unavailable:       "
        f"{failed}"
    )

    if total:

        recovery_rate = (
            recovered
            / total
            * 100
        )

        print(
            f"Recovery rate:           "
            f"{recovery_rate:.1f}%"
        )

    print_database_statistics()

    print(
        "=" * 70
    )


if __name__ == "__main__":
    main()