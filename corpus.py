import time
from datetime import datetime

from database import (
    create_database,
    save_article,
    update_full_text,
    has_full_text,
    create_search,
    update_search,
    log_download_failure,
    clear_download_failure,
    get_database_statistics,
)

from pubmed import (
    search_pubmed,
    fetch_articles,
)

from pmc import download_article


# ============================================================
# CONFIGURATION
# ============================================================

METADATA_BATCH_SIZE = 100

MAX_RETRIES = 3

# Waiting time between ordinary requests.
REQUEST_DELAY = 0.4


# ============================================================
# INPUT HELPERS
# ============================================================

def read_integer(prompt, default=None):
    """
    Read an integer from the user.

    Pressing Enter returns the supplied default value.
    """

    while True:

        value = input(prompt).strip()

        if not value:
            return default

        try:
            return int(value)

        except ValueError:
            print(
                "Please enter an integer "
                "or press Enter."
            )


def read_yes_no(prompt, default=True):
    """
    Read a yes/no answer.
    """

    while True:

        value = input(prompt).strip().lower()

        if not value:
            return default

        if value in ("y", "yes"):
            return True

        if value in ("n", "no"):
            return False

        print(
            "Please enter y or n."
        )


# ============================================================
# FULL-TEXT DOWNLOAD WITH RETRY
# ============================================================

def download_with_retry(article):
    """
    Try to download a full-text article several times.

    Returns:
        result, attempts, error_message
    """

    pmid = article["pmid"]

    result = None
    last_error = None

    for attempt in range(
        1,
        MAX_RETRIES + 1,
    ):

        print(
            f"  Download attempt "
            f"{attempt}/{MAX_RETRIES}"
        )

        try:

            result = download_article(
                pmid,
                article.copy(),
            )

            if result:

                return (
                    result,
                    attempt,
                    None,
                )

            last_error = (
                "download_article returned "
                "no result"
            )

        except Exception as error:

            last_error = str(error)

            print(
                f"  Download error: "
                f"{last_error}"
            )

        # ----------------------------------------------------
        # RETRY DELAY
        # ----------------------------------------------------

        if attempt < MAX_RETRIES:

            wait_seconds = (
                2 ** attempt
            )

            print(
                f"  Retrying in "
                f"{wait_seconds} seconds..."
            )

            time.sleep(
                wait_seconds
            )

    return (
        None,
        MAX_RETRIES,
        last_error,
    )


# ============================================================
# PROCESS SINGLE ARTICLE
# ============================================================

def process_article(
    article,
    current_number,
    total_number,
):
    """
    Save article metadata and obtain full text when available.

    Returns one of:

        "downloaded"
        "existing"
        "failed"
    """

    pmid = article["pmid"]

    title = (
        article.get("title")
        or ""
    )

    pmcid = article.get(
        "pmcid"
    )

    print()
    print(
        f"[{current_number}/{total_number}] "
        f"PMID {pmid}"
    )

    print(
        f"  {title[:100]}"
    )

    if pmcid:

        print(
            f"  PMCID: {pmcid}"
        )

    # --------------------------------------------------------
    # SAVE / UPDATE METADATA
    # --------------------------------------------------------

    save_article(
        article
    )

    # --------------------------------------------------------
    # FULL TEXT ALREADY EXISTS
    # --------------------------------------------------------

    if has_full_text(
        pmid
    ):

        print(
            "  Full text already "
            "stored in database."
        )

        # A previous failure record is no longer relevant.
        clear_download_failure(
            pmid
        )

        return "existing"

    # --------------------------------------------------------
    # DOWNLOAD FULL TEXT
    # --------------------------------------------------------

    result, attempts, error_message = ( #attempts
        download_with_retry(
            article
        )
    )

    # --------------------------------------------------------
    # SUCCESS
    # --------------------------------------------------------

    if result:

        full_text = result.get(
            "full_text",
            ""
        )

        result_pmcid = result.get(
            "pmcid"
        )

        if not full_text.strip():

            error_message = (
                "Downloaded article "
                "contains empty full text."
            )

        else:

            update_full_text(
                pmid,
                result_pmcid,
                full_text,
            )

            clear_download_failure(
                pmid
            )

            print(
                f"  Stored in SQLite: "
                f"{len(full_text):,} characters"
            )

            return "downloaded"

    # --------------------------------------------------------
    # FAILURE
    # --------------------------------------------------------

    if not error_message:

        error_message = (
            "Unknown full-text "
            "download failure."
        )

    print(
        "  Full-text download failed "
        "after all attempts."
    )

    log_download_failure(
        pmid=pmid,
        pmcid=pmcid,
        stage="full_text",
        error_message=error_message,
    )

    return "failed"


# ============================================================
# CORPUS BUILDER
# ============================================================

def main():

    # --------------------------------------------------------
    # INITIALIZE DATABASE
    # --------------------------------------------------------

    create_database()

    print()
    print("=" * 70)
    print(
        "          PubMed Research Corpus Builder"
    )
    print("=" * 70)
    print()

    # --------------------------------------------------------
    # USER INPUT
    # --------------------------------------------------------

    query = input(
        "PubMed query: "
    ).strip()

    if not query:

        print(
            "Search query cannot be empty."
        )

        return

    start_year = read_integer(
        "Start year "
        "[Enter = no limit]: "
    )

    end_year = read_integer(
        "End year "
        f"[Enter = {datetime.now().year}]: ", ###problem z rokiem wystąpi bo pobiera lokalny
        datetime.now().year,
    )

    max_results = read_integer(
        "Maximum number of articles "
        "[1000]: ",
        1000,
    )

    pmc_only = read_yes_no(
        "PMC Open Access full text only? "
        "[Y/n]: ",
        True,
    )

    # --------------------------------------------------------
    # SEARCH SUMMARY
    # --------------------------------------------------------

    print()
    print("-" * 70)
    print("SEARCH CONFIGURATION")
    print("-" * 70)

    print(
        f"Query:          {query}"
    )

    print(
        f"Start year:     "
        f"{start_year or 'no limit'}"
    )

    print(
        f"End year:       {end_year}"
    )

    print(
        f"Maximum:        {max_results:,}"
    )

    print(
        "PMC OA only:    "
        f"{'yes' if pmc_only else 'no'}"
    )

    print("-" * 70)

    # --------------------------------------------------------
    # PUBMED SEARCH
    # --------------------------------------------------------

    print()
    print(
        "Searching PubMed..."
    )

    pmids, total, final_query = (
        search_pubmed(
            query=query,
            start_year=start_year,
            end_year=end_year,
            pmc_only=pmc_only,
            max_results=max_results,
            batch_size=100,
        )
    )

    if total is None:
        total = 0

    if not pmids:

        print()
        print(
            "No PubMed records found."
        )

        return

    requested = min(
        max_results,
        total,
    )

    # --------------------------------------------------------
    # REGISTER SEARCH
    # --------------------------------------------------------

    search_id = create_search(
        final_query,
        start_year,
        end_year,
        pmc_only,
        total,
        requested,
    )

    # --------------------------------------------------------
    # RUN STATISTICS
    # --------------------------------------------------------

    retrieved = 0

    newly_downloaded = 0

    already_existing = 0

    failed = 0

    # --------------------------------------------------------
    # PROCESS METADATA IN BATCHES
    # --------------------------------------------------------

    number_of_batches = (
        len(pmids)
        + METADATA_BATCH_SIZE
        - 1
    ) // METADATA_BATCH_SIZE

    print()
    print(
        f"Processing {len(pmids):,} "
        f"PubMed records in "
        f"{number_of_batches} batch(es)."
    )

    for start in range(
        0,
        len(pmids),
        METADATA_BATCH_SIZE,
    ):

        batch_pmids = pmids[
            start:
            start + METADATA_BATCH_SIZE
        ]

        batch_number = (
            start //
            METADATA_BATCH_SIZE
        ) + 1

        print()
        print("=" * 70)

        print(
            f"METADATA BATCH "
            f"{batch_number}/"
            f"{number_of_batches}"
        )

        print("=" * 70)

        # ----------------------------------------------------
        # FETCH PUBMED METADATA
        # ----------------------------------------------------

        try:

            articles = fetch_articles(
                batch_pmids
            )

        except Exception as error:

            print(
                f"Metadata batch failed: "
                f"{error}"
            )

            # Record every PMID from the failed batch.
            for pmid in batch_pmids:

                log_download_failure(
                    pmid=pmid,
                    pmcid=None,
                    stage="metadata",
                    error_message=str(error),
                )

            continue

        # ----------------------------------------------------
        # PROCESS ARTICLES
        # ----------------------------------------------------

        for article in articles:

            retrieved += 1

            try:

                status = process_article(
                    article,
                    retrieved,
                    len(pmids),
                )

            except Exception as error:

                status = "failed"

                print(
                    f"  Unexpected error: "
                    f"{error}"
                )

                log_download_failure(
                    pmid=article["pmid"],
                    pmcid=article.get(
                        "pmcid"
                    ),
                    stage="processing",
                    error_message=str(error),
                )

            if status == "downloaded":

                newly_downloaded += 1

            elif status == "existing":

                already_existing += 1

            elif status == "failed":

                failed += 1

            # ------------------------------------------------
            # UPDATE SEARCH PROGRESS
            # ------------------------------------------------

            update_search(
                search_id,
                retrieved,
                newly_downloaded,
            )

            # ------------------------------------------------
            # REQUEST DELAY
            # ------------------------------------------------

            time.sleep(
                REQUEST_DELAY
            )

        # Delay between metadata batches.
        time.sleep(
            REQUEST_DELAY
        )

    # --------------------------------------------------------
    # DATABASE-WIDE STATISTICS
    # --------------------------------------------------------

    database_stats = (
        get_database_statistics()
    )

    # --------------------------------------------------------
    # FINAL REPORT
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print(
        "CORPUS BUILD COMPLETED"
    )
    print("=" * 70)
    print()

    print(
        f"PubMed records found:       "
        f"{total:,}"
    )

    print(
        f"Records requested:          "
        f"{requested:,}"
    )

    print(
        f"Metadata retrieved:         "
        f"{retrieved:,}"
    )

    print(
        f"New full texts downloaded:  "
        f"{newly_downloaded:,}"
    )

    print(
        f"Already in database:        "
        f"{already_existing:,}"
    )

    print(
        f"Failed full-text downloads: "
        f"{failed:,}"
    )

    print()
    print("-" * 70)
    print(
        "ENTIRE DATABASE"
    )
    print("-" * 70)

    print(
        f"Total articles:             "
        f"{database_stats['total_articles']:,}"
    )

    print(
        f"Articles with PMCID:        "
        f"{database_stats['pmc_articles']:,}"
    )

    print(
        f"Articles with full text:    "
        f"{database_stats['full_text_articles']:,}"
    )

    print()
    print(
        f"Search ID: {search_id}"
    )

    print("=" * 70)


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    main()