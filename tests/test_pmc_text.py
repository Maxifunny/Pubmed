"""
PMC / BioC text helpers – local XML only.
"""

import pytest
import xml.etree.ElementTree as ET

from pmc import (
    local_name,
    clean_text,
    element_text,
    find_first,
    xml_to_text,
    bioc_xml_to_text,
    extract_article,
)


def test_local_name_strips_namespace():
    assert local_name("{http://example.org}article") == "article"
    assert local_name("body") == "body"


def test_clean_text():
    assert clean_text("  a   b\n\tc  ") == "a b c"
    assert clean_text("") == ""
    assert clean_text(None) == ""


def test_element_text_and_find_first():
    root = ET.fromstring(
        "<root><title>Hello   world</title><p>x</p></root>"
    )

    title = find_first(root, "title")
    assert element_text(title) == "Hello world"
    assert find_first(root, "missing") is None


def test_xml_to_text_basic_jats():
    xml = b"""<?xml version="1.0"?>
    <article>
      <front>
        <article-meta>
          <title-group>
            <article-title>Example PDE4 study</article-title>
          </title-group>
          <abstract><p>Short abstract here.</p></abstract>
        </article-meta>
      </front>
      <body>
        <sec>
          <title>Results</title>
          <p>Compound X inhibits PDE4 with IC50 of 12 nM.</p>
        </sec>
      </body>
    </article>
    """

    text = xml_to_text(xml)

    assert "Example PDE4 study" in text
    assert "ABSTRACT" in text
    assert "Short abstract here." in text
    assert "RESULTS" in text
    assert "IC50 of 12 nM" in text


def test_xml_to_text_empty_raises():
    with pytest.raises(ValueError, match="No text extracted"):
        xml_to_text(b"<article></article>")


def test_bioc_xml_to_text():
    xml = b"""<?xml version="1.0"?>
    <collection>
      <document>
        <passage>
          <infon key="section_type">abstract</infon>
          <text>BioC abstract sentence.</text>
        </passage>
        <passage>
          <infon key="type">paragraph</infon>
          <text>Main findings about inhibition.</text>
        </passage>
      </document>
    </collection>
    """

    text = bioc_xml_to_text(xml)

    assert "[ABSTRACT]" in text
    assert "BioC abstract sentence." in text
    assert "Main findings about inhibition." in text


def test_extract_article_from_oai_wrapper():
    xml = b"""<?xml version="1.0"?>
    <OAI-PMH>
      <GetRecord>
        <record>
          <metadata>
            <article>
              <body><p>inside</p></body>
            </article>
          </metadata>
        </record>
      </GetRecord>
    </OAI-PMH>
    """

    article_xml = extract_article(xml)
    assert b"<article>" in article_xml
    assert b"inside" in article_xml


def test_extract_article_oai_error():
    xml = b"""<?xml version="1.0"?>
    <OAI-PMH>
      <error code="idDoesNotExist">bad id</error>
    </OAI-PMH>
    """

    with pytest.raises(ValueError, match="OAI error"):
        extract_article(xml)
