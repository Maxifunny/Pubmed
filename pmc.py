import json
import os
import re
import time
import xml.etree.ElementTree as ET

import requests
from get_env import loading_enviroment
import os

# ============================================================
# CONFIGURATION
# ============================================================

IDCONV_URL = "https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/"

PMC_OAI_URL = "https://pmc.ncbi.nlm.nih.gov/api/oai/v1/mh/"

BIOC_BASE_URL = (
    "https://www.ncbi.nlm.nih.gov/research/bionlp/"
    "RESTful/pmcoa.cgi"
)

TOOL = "pubmed_research"

# IMPORTANT:
# Replace this with the same e-mail address used in pubmed.py
loading_enviroment()
EMAIL = os.getenv("EMAIL")



REQUEST_TIMEOUT = 60

ARTICLES_DIR = "articles"


# ============================================================
# HTTP SESSION
# ============================================================

session = requests.Session()

session.headers.update({
    "User-Agent": f"{TOOL}/1.0 ({EMAIL})"
})


# ============================================================
# XML HELPERS
# ============================================================

def local_name(tag):
    """
    Remove XML namespace from a tag.
    """

    if "}" in tag:
        return tag.split("}", 1)[1]

    return tag


def clean_text(text):
    """
    Normalize whitespace.
    """

    if not text:
        return ""

    return re.sub(
        r"\s+",
        " ",
        text
    ).strip()


def element_text(element):
    """
    Extract all text contained inside an XML element.
    """

    if element is None:
        return ""

    return clean_text(
        " ".join(element.itertext())
    )


def find_first(root, tag_name):
    """
    Find the first element with the specified local tag name.
    """

    for element in root.iter():

        if local_name(element.tag) == tag_name:
            return element

    return None


# ============================================================
# PMID -> PMCID
# ============================================================

def get_pmcid(pmid):
    """
    Convert PMID to PMCID using the NCBI ID Converter API.
    """

    params = {
        "ids": pmid,
        "format": "json",
        "tool": TOOL,
        "email": EMAIL
    }

    response = session.get(
        IDCONV_URL,
        params=params,
        timeout=REQUEST_TIMEOUT
    )

    response.raise_for_status()

    data = response.json()

    records = data.get(
        "records",
        []
    )

    if not records:
        return None

    return records[0].get(
        "pmcid"
    )


# ============================================================
# PMC OAI-PMH
# ============================================================

def download_pmc_xml(pmcid):
    """
    Download article XML using PMC OAI-PMH.
    """

    numeric_pmcid = (
        pmcid.upper()
        .replace("PMC", "")
    )

    params = {
        "verb": "GetRecord",
        "identifier": (
            "oai:pubmedcentral.nih.gov:"
            f"{numeric_pmcid}"
        ),
        "metadataPrefix": "pmc"
    }

    response = session.get(
        PMC_OAI_URL,
        params=params,
        timeout=REQUEST_TIMEOUT
    )

    response.raise_for_status()

    return response.content


def extract_article(xml_content):
    """
    Extract the JATS <article> element from an OAI response.
    """

    root = ET.fromstring(
        xml_content
    )

    # Check for an OAI error.
    for element in root.iter():

        if local_name(element.tag) == "error":

            error_code = element.attrib.get(
                "code",
                "unknown"
            )

            error_text = element_text(
                element
            )

            raise ValueError(
                f"OAI error {error_code}: "
                f"{error_text}"
            )

    article = find_first(
        root,
        "article"
    )

    if article is None:

        raise ValueError(
            "No JATS <article> element found "
            "in the OAI response."
        )

    return ET.tostring(
        article,
        encoding="utf-8",
        xml_declaration=True
    )


# ============================================================
# JATS XML -> TEXT
# ============================================================

def process_section(section, output):
    """
    Recursively extract text from a JATS section.
    """

    title = None

    for child in section:

        if local_name(child.tag) == "title":

            title = element_text(
                child
            )

            break

    if title:

        output.append("")
        output.append(
            title.upper()
        )
        output.append("")

    for child in section:

        tag = local_name(
            child.tag
        )

        if tag == "p":

            text = element_text(
                child
            )

            if text:
                output.append(
                    text
                )

        elif tag == "sec":

            process_section(
                child,
                output
            )


def xml_to_text(article_xml):
    """
    Convert JATS article XML into plain text.
    """

    root = ET.fromstring(
        article_xml
    )

    output = []

    # --------------------------------------------------------
    # TITLE
    # --------------------------------------------------------

    article_title = find_first(
        root,
        "article-title"
    )

    title = element_text(
        article_title
    )

    if title:

        output.append(
            title
        )

        output.append("")

        output.append(
            "=" * 70
        )

        output.append("")

    # --------------------------------------------------------
    # ABSTRACT
    # --------------------------------------------------------

    abstract = find_first(
        root,
        "abstract"
    )

    if abstract is not None:

        abstract_text = element_text(
            abstract
        )

        if abstract_text:

            output.append(
                "ABSTRACT"
            )

            output.append("")

            output.append(
                abstract_text
            )

            output.append("")

    # --------------------------------------------------------
    # BODY
    # --------------------------------------------------------

    body = find_first(
        root,
        "body"
    )

    if body is not None:

        output.append(
            "BODY"
        )

        output.append("")

        sections_found = False

        for child in body:

            tag = local_name(
                child.tag
            )

            if tag == "sec":

                sections_found = True

                process_section(
                    child,
                    output
                )

            elif tag == "p":

                text = element_text(
                    child
                )

                if text:

                    output.append(
                        text
                    )

        # Fallback for unusual JATS structure.
        if not sections_found:

            body_text = element_text(
                body
            )

            if body_text:

                output.append(
                    body_text
                )

    full_text = "\n\n".join(
        output
    )

    full_text = re.sub(
        r"\n{3,}",
        "\n\n",
        full_text
    )

    full_text = full_text.strip()

    if not full_text:

        raise ValueError(
            "No text extracted from JATS XML."
        )

    return full_text


# ============================================================
# BioC API
# ============================================================

def download_bioc_xml(pmcid):
    """
    Download a PMC article using the BioC API.

    Handles:
        - HTTP 429 rate limiting
        - transient 5xx errors
        - HTML responses
        - invalid XML
    """

    url = (
        f"{BIOC_BASE_URL}/"
        f"BioC_xml/{pmcid}/unicode"
    )

    max_attempts = 5

    for attempt in range(
        1,
        max_attempts + 1
    ):

        print(
            f"  Trying BioC API: {pmcid} "
            f"(attempt {attempt}/{max_attempts})"
        )

        response = session.get(
            url,
            timeout=REQUEST_TIMEOUT
        )

        status = (
            response.status_code
        )

        print(
            f"  BioC HTTP status: {status}"
        )

        # ====================================================
        # HTTP 200
        # ====================================================

        if status == 200:

            content = response.content

            if not content:

                raise ValueError(
                    "BioC returned an empty response."
                )

            content_type = (
                response.headers.get(
                    "Content-Type",
                    ""
                )
            )

            print(
                "  BioC Content-Type: "
                f"{content_type}"
            )

            beginning = (
                content
                .lstrip()[:100]
                .lower()
            )

            # BioC should not return HTML.
            if (
                beginning.startswith(
                    b"<!doctype html"
                )
                or beginning.startswith(
                    b"<html"
                )
            
            ):
            #if beginning.startswith((b"<!doctype html", b"<html")):
                preview = (
                    response.text[:300]
                )

                raise ValueError(
                    "BioC returned HTML "
                    "instead of XML. "
                    f"Response: {preview!r}"
                )

            # Validate XML.
            try:

                ET.fromstring(
                    content
                )

            except ET.ParseError as error:

                preview = (
                    response.text[:300]
                )

                raise ValueError(
                    "BioC returned a non-XML "
                    "response. "
                    f"Beginning of response: "
                    f"{preview!r}"
                ) from error

            return content

        # ====================================================
        # HTTP 429
        # ====================================================

        if status == 429:

            print(
                "  BioC rate limit reached."
            )

            retry_after = (
                response.headers.get(
                    "Retry-After"
                )
            )

            try:

                wait_time = float(
                    retry_after
                )

            except (
                TypeError,
                ValueError
            ):

                # Increasing wait:
                # 5, 10, 15, 20, 25 seconds
                wait_time = (
                    5 * attempt
                )

            # Never retry immediately.
            wait_time = max(
                wait_time,
                5
            )

            if attempt < max_attempts:

                print(
                    f"  Waiting "
                    f"{wait_time:.0f} seconds..."
                )

                time.sleep(
                    wait_time
                )

                continue

            raise RuntimeError(
                "BioC rate limit exceeded "
                "after all retry attempts."
            )

        # ====================================================
        # TEMPORARY SERVER ERRORS
        # ====================================================

        if status in (
            500,
            502,
            503,
            504
        ):

            print(
                "  Temporary BioC "
                f"server error {status}."
            )

            wait_time = (
                5 * attempt
            )

            if attempt < max_attempts:

                print(
                    f"  Waiting "
                    f"{wait_time} seconds..."
                )

                time.sleep(
                    wait_time
                )

                continue

            raise RuntimeError(
                "BioC server error "
                f"{status} after all "
                "retry attempts."
            )

        # ====================================================
        # OTHER HTTP ERRORS
        # ====================================================

        preview = (
            response.text[:300]
        )

        raise RuntimeError(
            f"BioC returned HTTP {status}. "
            f"Response: {preview!r}"
        )

    raise RuntimeError(
        "BioC download failed."
    )


# ============================================================
# BioC XML -> TEXT
# ============================================================

def bioc_xml_to_text(xml_content):
    """
    Convert BioC XML into plain text.
    """

    root = ET.fromstring(
        xml_content
    )

    output = []

    for passage in root.iter():

        if (
            local_name(passage.tag)
            != "passage"
        ):
            continue

        section_type = None
        passage_text = None

        for child in passage:

            tag = local_name(
                child.tag
            )

            if tag == "infon":

                key = (
                    child.attrib.get(
                        "key",
                        ""
                    )
                )

                if key in (
                    "section_type",
                    "type"
                ):

                    section_type = (
                        element_text(
                            child
                        )
                    )

            elif tag == "text":

                passage_text = (
                    element_text(
                        child
                    )
                )

        if not passage_text:
            continue

        if section_type:

            output.append(
                f"[{section_type.upper()}]"
            )

        output.append(
            passage_text
        )

    full_text = "\n\n".join(
        output
    )

    full_text = re.sub(
        r"\n{3,}",
        "\n\n",
        full_text
    )

    full_text = full_text.strip()

    if not full_text:

        raise ValueError(
            "No article text found "
            "in BioC response."
        )

    return full_text


# ============================================================
# SAVE ARTICLE
# ============================================================

def save_pmc_article(
    pmid,
    pmcid,
    xml_content,
    full_text,
    source="oai"
):
    """
    Save XML, TXT and metadata.json locally.
    """

    article_dir = os.path.join(
        ARTICLES_DIR,
        pmcid
    )

    os.makedirs(
        article_dir,
        exist_ok=True
    )

    # --------------------------------------------------------
    # XML
    # --------------------------------------------------------

    xml_path = os.path.join(
        article_dir,
        "article.xml"
    )

    with open(
        xml_path,
        "wb"
    ) as file:

        file.write(
            xml_content
        )

    # --------------------------------------------------------
    # TXT
    # --------------------------------------------------------

    txt_path = os.path.join(
        article_dir,
        "article.txt"
    )

    with open(
        txt_path,
        "w",
        encoding="utf-8"
    ) as file:

        file.write(
            full_text
        )

    # --------------------------------------------------------
    # METADATA
    # --------------------------------------------------------

    metadata_path = os.path.join(
        article_dir,
        "metadata.json"
    )

    metadata = {
        "pmid": pmid,
        "pmcid": pmcid,
        "source": source
    }

    with open(
        metadata_path,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            metadata,
            file,
            indent=2,
            ensure_ascii=False
        )

    print(
        f"  Files saved in: "
        f"{article_dir}"
    )


# ============================================================
# DOWNLOAD ARTICLE
# ============================================================

def download_article(
    pmid,
    metadata=None
):
    """
    Download article full text.

    Strategy:
        1. Use PMCID from metadata if available.
        2. Otherwise obtain PMCID using ID Converter.
        3. Try OAI-PMH.
        4. If OAI fails, try BioC.
    """

    print(
        f"Checking PMID {pmid}..."
    )

    pmcid = None

    if metadata:

        pmcid = metadata.get(
            "pmcid"
        )

    # --------------------------------------------------------
    # PMCID
    # --------------------------------------------------------

    if pmcid:

        print(
            "  PMCID already available: "
            f"{pmcid}"
        )

    else:

        print(
            "  Searching for PMCID..."
        )

        pmcid = get_pmcid(
            pmid
        )

        if not pmcid:

            raise ValueError(
                "No PMCID found for "
                f"PMID {pmid}."
            )

        print(
            f"  PMCID found: {pmcid}"
        )

    # ========================================================
    # METHOD 1: OAI-PMH
    # ========================================================

    try:

        print(
            "  Downloading JATS XML: "
            f"{pmcid}"
        )

        oai_xml = (
            download_pmc_xml(
                pmcid
            )
        )

        article_xml = (
            extract_article(
                oai_xml
            )
        )

        full_text = (
            xml_to_text(
                article_xml
            )
        )

        save_pmc_article(
            pmid=pmid,
            pmcid=pmcid,
            xml_content=article_xml,
            full_text=full_text,
            source="oai"
        )

        print(
            "  Full text downloaded "
            "using OAI-PMH."
        )

        return {
            "pmid": pmid,
            "pmcid": pmcid,
            "full_text": full_text,
            "xml": article_xml,
            "source": "oai"
        }

    except Exception as error:

        print(
            f"  OAI failed: {error}"
        )

        print(
            "  Falling back to BioC..."
        )

    # ========================================================
    # METHOD 2: BioC
    # ========================================================

    try:

        bioc_xml = (
            download_bioc_xml(
                pmcid
            )
        )

        full_text = (
            bioc_xml_to_text(
                bioc_xml
            )
        )

        save_pmc_article(
            pmid=pmid,
            pmcid=pmcid,
            xml_content=bioc_xml,
            full_text=full_text,
            source="bioc"
        )

        print(
            "  Full text downloaded "
            "using BioC."
        )

        return {
            "pmid": pmid,
            "pmcid": pmcid,
            "full_text": full_text,
            "xml": bioc_xml,
            "source": "bioc"
        }

    except Exception as error:

        print(
            f"  BioC failed: {error}"
        )

        raise RuntimeError(
            "Both OAI and BioC failed "
            f"for {pmcid}. "
            f"Last error: {error}"
        )


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    print(
        "=" * 70
    )

    print(
        "PMC FULL-TEXT DOWNLOADER"
    )

    print(
        "=" * 70
    )

    pmid = input(
        "Enter PMID: "
    ).strip()

    if not pmid:

        print(
            "No PMID provided."
        )

        raise SystemExit(1)

    try:

        result = download_article(
            pmid
        )

        print()

        print(
            "=" * 70
        )

        print(
            "DOWNLOAD SUCCESSFUL"
        )

        print(
            "=" * 70
        )

        print(
            f"PMID:   "
            f"{result['pmid']}"
        )

        print(
            f"PMCID:  "
            f"{result['pmcid']}"
        )

        print(
            f"Source: "
            f"{result['source']}"
        )

        print(
            "Text length: "
            f"{len(result['full_text']):,} "
            "characters"
        )

    except Exception as error:

        print()

        print(
            "=" * 70
        )

        print(
            "DOWNLOAD FAILED"
        )

        print(
            "=" * 70
        )

        print(
            str(error)
        )