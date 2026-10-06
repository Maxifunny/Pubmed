"""
Candidate sentence extraction for Knowledge Graph v4.1.

Pilot article:
    article_id = 614
    PMID       = 41752476

This script DOES NOT modify the knowledge graph.
It only identifies potentially useful sentences for
drug-discovery relation extraction.
"""

import re
import sqlite3


DATABASE = "pubmed.db"

ARTICLE_ID = 614


# ------------------------------------------------------------
# Drug-discovery vocabulary
# ------------------------------------------------------------

ACTIVITY_PATTERN = re.compile(
    r"\b("
    r"IC[\s\-]?50|"
    r"EC[\s\-]?50|"
    r"GI[\s\-]?50|"
    r"ED[\s\-]?50|"
    r"Ki|Kd|MIC"
    r")\b",
    re.IGNORECASE,
)


RELATION_PATTERN = re.compile(
    r"\b("
    r"inhibit(?:s|ed|ing|ion)?|"
    r"bind(?:s|ing)?|"
    r"bound|"
    r"target(?:s|ed|ing)?|"
    r"activat(?:e|es|ed|ing|ion)|"
    r"antagonist(?:s)?|"
    r"agonist(?:s)?|"
    r"affinity|"
    r"potency|"
    r"selectiv(?:e|ity)|"
    r"activity"
    r")\b",
    re.IGNORECASE,
)


METHOD_PATTERN = re.compile(
    r"\b("
    r"molecular docking|"
    r"docking|"
    r"molecular dynamics|"
    r"\bMD\b|"
    r"in vitro|"
    r"in vivo|"
    r"assay|"
    r"binding assay|"
    r"enzyme assay|"
    r"cell(?:ular)? assay|"
    r"virtual screening"
    r")\b",
    re.IGNORECASE,
)


VALUE_PATTERN = re.compile(
    r"(?:IC[\s\-]?50|EC[\s\-]?50|GI[\s\-]?50|"
    r"ED[\s\-]?50|Ki|Kd|MIC)"
    r".{0,40}?"
    r"(?:=|of|was|were|:)?\s*"
    r"([<>≤≥~]?\s*\d+(?:\.\d+)?)"
    r"\s*"
    r"(pM|nM|µM|μM|uM|mM|M)\b",
    re.IGNORECASE,
)


# ------------------------------------------------------------
# Database
# ------------------------------------------------------------

def get_article(article_id):

    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            id,
            pmid,
            pmcid,
            title,
            full_text
        FROM articles
        WHERE id = ?
        """,
        (article_id,),
    )

    article = cursor.fetchone()

    connection.close()

    return article


# ------------------------------------------------------------
# Sentence segmentation
# ------------------------------------------------------------

def split_sentences(text):
    """
    Lightweight sentence segmentation.

    This is intentionally conservative for the pilot.
    A biomedical NLP sentence segmenter can replace it later.
    """

    text = text.replace("\r", "\n")

    text = re.sub(
        r"\n+",
        " ",
        text,
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    sentences = re.split(
        r"(?<=[.!?])\s+(?=[A-Z0-9])",
        text,
    )

    return [
        sentence.strip()
        for sentence in sentences
        if len(sentence.strip()) >= 30
    ]


# ------------------------------------------------------------
# Candidate scoring
# ------------------------------------------------------------

def classify_sentence(sentence):

    activity = bool(
        ACTIVITY_PATTERN.search(sentence)
    )

    relation = bool(
        RELATION_PATTERN.search(sentence)
    )

    method = bool(
        METHOD_PATTERN.search(sentence)
    )

    quantitative = bool(
        VALUE_PATTERN.search(sentence)
    )

    score = 0

    if activity:
        score += 3

    if quantitative:
        score += 4

    if relation:
        score += 2

    if method:
        score += 1

    return {
        "activity": activity,
        "quantitative": quantitative,
        "relation": relation,
        "method": method,
        "score": score,
    }


# ------------------------------------------------------------
# Extraction
# ------------------------------------------------------------

def extract_candidates(text):

    sentences = split_sentences(text)

    candidates = []

    for index, sentence in enumerate(
        sentences,
        start=1,
    ):

        classification = classify_sentence(
            sentence
        )

        # At least one drug-discovery signal required.
        if classification["score"] == 0:
            continue

        candidates.append(
            {
                "sentence_number": index,
                "sentence": sentence,
                **classification,
            }
        )

    candidates.sort(
        key=lambda item: item["score"],
        reverse=True,
    )

    return sentences, candidates


# ------------------------------------------------------------
# Display
# ------------------------------------------------------------

def print_candidate(candidate):

    labels = []

    if candidate["activity"]:
        labels.append("ACTIVITY")

    if candidate["quantitative"]:
        labels.append("VALUE")

    if candidate["relation"]:
        labels.append("RELATION")

    if candidate["method"]:
        labels.append("METHOD")

    print()
    print("-" * 80)

    print(
        f"Sentence: "
        f"{candidate['sentence_number']}"
    )

    print(
        f"Score:    "
        f"{candidate['score']}"
    )

    print(
        f"Signals:  "
        f"{', '.join(labels)}"
    )

    print()

    print(
        candidate["sentence"]
    )


# ------------------------------------------------------------
# Main
# ------------------------------------------------------------

def main():

    article = get_article(
        ARTICLE_ID
    )

    if article is None:

        print(
            f"Article ID {ARTICLE_ID} "
            "not found."
        )

        return

    if not article["full_text"]:

        print(
            "Article does not contain "
            "full text."
        )

        return

    print(
        "=" * 80
    )

    print(
        "KG v4.1 — CANDIDATE EXTRACTION"
    )

    print(
        "=" * 80
    )

    print(
        f"Article ID: {article['id']}"
    )

    print(
        f"PMID:       {article['pmid']}"
    )

    print(
        f"PMCID:      {article['pmcid']}"
    )

    print()

    print(
        article["title"]
    )

    sentences, candidates = (
        extract_candidates(
            article["full_text"]
        )
    )

    print()
    print(
        f"Text length:          "
        f"{len(article['full_text']):,}"
    )

    print(
        f"Sentences detected:   "
        f"{len(sentences):,}"
    )

    print(
        f"Candidate sentences:  "
        f"{len(candidates):,}"
    )

    print()
    print(
        "=" * 80
    )

    print(
        "TOP CANDIDATE SENTENCES"
    )

    print(
        "=" * 80
    )

    # First examine the 30 strongest candidates.
    for candidate in candidates[:30]:

        print_candidate(
            candidate
        )


if __name__ == "__main__":
    main()