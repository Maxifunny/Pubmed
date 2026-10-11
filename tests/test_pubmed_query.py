"""
Unit tests for PubMed query construction.
"""

from pubmed import build_query


def test_build_query_basic():
    result = build_query("PDE4 inhibitor")

    assert result == "(PDE4 inhibitor)"


def test_build_query_with_year_range():
    result = build_query(
        "drug repurposing",
        start_year=2018,
        end_year=2024,
    )

    assert result == (
        '(drug repurposing) AND '
        '("2018"[Date - Publication] : '
        '"2024"[Date - Publication])'
    )


def test_build_query_only_start_year_uses_default_end():
    result = build_query(
        "IC50",
        start_year=2020,
    )

    assert '"2020"[Date - Publication]' in result
    assert '"3000"[Date - Publication]' in result


def test_build_query_only_end_year_uses_default_start():
    result = build_query(
        "IC50",
        end_year=2015,
    )

    assert '"1900"[Date - Publication]' in result
    assert '"2015"[Date - Publication]' in result


def test_build_query_pmc_only_adds_filter():
    result = build_query(
        "kinase",
        pmc_only=True,
    )

    assert result == (
        '(kinase) AND '
        '"pubmed pmc open access"[Filter]'
    )


def test_build_query_full_combination():
    result = build_query(
        "PDE4",
        start_year=2010,
        end_year=2020,
        pmc_only=True,
    )

    assert result.startswith("(PDE4) AND ")
    assert "[Date - Publication]" in result
    assert result.endswith('"pubmed pmc open access"[Filter]')