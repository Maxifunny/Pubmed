import time
import requests
import xml.etree.ElementTree as ET
from get_env import loading_enviroment
import os

BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

TOOL = "pubmed_research"

loading_enviroment()
EMAIL = os.getenv("EMAIL")


# Replace with your own e-mail.


REQUEST_TIMEOUT = 60


def build_query(
    query,
    start_year=None,
    end_year=None,
    pmc_only=False,
):
    parts = [
        f"({query})"
    ]

    if start_year or end_year:

        start = start_year or 1900
        end = end_year or 3000

        parts.append(
            f'("{start}"[Date - Publication] : '
            f'"{end}"[Date - Publication])'
        )

    if pmc_only:
        parts.append(
            '"pubmed pmc open access"[Filter]'
        )

    return " AND ".join(parts)


def search_pubmed(
    query,
    start_year=None,
    end_year=None,
    pmc_only=False,
    max_results=1000,
    batch_size=100,
):
    final_query = build_query(
        query,
        start_year,
        end_year,
        pmc_only,
    )

    print()
    print("PubMed query:")
    print(final_query)
    print()

    pmids = []
    total = None

    retstart = 0

    while len(pmids) < max_results:

        remaining = (
            max_results - len(pmids)
        )

        current_batch = min(
            batch_size,
            remaining
        )

        params = {
            "db": "pubmed",
            "term": final_query,
            "retstart": retstart,
            "retmax": current_batch,
            "retmode": "json",
            "sort": "relevance",
            "tool": TOOL,
            "email": EMAIL,
        }

        response = requests.get(
            f"{BASE_URL}/esearch.fcgi",
            params=params,
            timeout=REQUEST_TIMEOUT,
        )

        response.raise_for_status()

        data = response.json()

        result = data["esearchresult"]

        if total is None:
            total = int(
                result["count"]
            )

            print(
                f"PubMed found "
                f"{total:,} records."
            )

        batch_pmids = result["idlist"]

        if not batch_pmids:
            break

        pmids.extend(
            batch_pmids
        )

        print(
            f"Retrieved PMID list: "
            f"{len(pmids):,}"
        )

        retstart += len(
            batch_pmids
        )

        if retstart >= total:
            break

        time.sleep(0.4)  #Sleep

    return pmids, total, final_query


def fetch_articles(pmids):
    if not pmids:
        return []

    params = {
        "db": "pubmed",
        "id": ",".join(pmids),
        "retmode": "xml",
        "tool": TOOL,
        "email": EMAIL,
    }

    response = requests.get(
        f"{BASE_URL}/efetch.fcgi",
        params=params,
        timeout=REQUEST_TIMEOUT,
    )

    response.raise_for_status()

    root = ET.fromstring(
        response.content
    )

    articles = []

    for record in root.findall(
        ".//PubmedArticle"
    ):

        citation = record.find(
            "MedlineCitation"
        )

        if citation is None:
            continue

        pmid = citation.findtext(
            "PMID"
        )

        article_node = citation.find(
            "Article"
        )

        if article_node is None:
            continue

        title_node = article_node.find(
            "ArticleTitle"
        )

        title = (
            "".join(title_node.itertext())
            if title_node is not None
            else ""
        )

        abstract_parts = []

        for abstract in article_node.findall(
            ".//Abstract/AbstractText"
        ):

            text = "".join(
                abstract.itertext()
            )

            label = abstract.attrib.get(
                "Label"
            )

            if label:
                text = (
                    f"{label}: {text}"
                )

            abstract_parts.append(
                text
            )

        abstract_text = "\n".join(
            abstract_parts
        )

        authors = []

        for author in article_node.findall(
            ".//AuthorList/Author"
        ):

            last_name = (
                author.findtext(
                    "LastName"
                )
                or ""
            )

            fore_name = (
                author.findtext(
                    "ForeName"
                )
                or ""
            )

            name = (
                f"{fore_name} "
                f"{last_name}"
            ).strip()

            if name:
                authors.append(name)

        authors_text = "; ".join(
            authors
        )

        journal = (
            article_node.findtext(
                ".//Journal/Title"
            )
            or ""
        )

        year = article_node.findtext(
            ".//JournalIssue/PubDate/Year"
        )

        if not year:

            medline_date = (
                article_node.findtext(
                    ".//JournalIssue/"
                    "PubDate/MedlineDate"
                )
            )

            if medline_date:
                year = medline_date[:4]
            else:
                year = ""

        doi = ""
        pmcid = None

        for article_id in record.findall(
            ".//PubmedData/"
            "ArticleIdList/ArticleId"
        ):

            id_type = (
                article_id.attrib.get(
                    "IdType"
                )
            )

            value = (
                article_id.text or ""
            )

            if id_type == "doi":
                doi = value

            elif id_type == "pmc":
                pmcid = value

        articles.append({
            "pmid": pmid,
            "pmcid": pmcid,
            "doi": doi,
            "title": title,
            "authors": authors_text,
            "journal": journal,
            "year": year,
            "abstract": abstract_text,
        })

    return articles