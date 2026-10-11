"""
SQLite helpers – on a temp db
"""

import database


def _use_temp_db(monkeypatch, tmp_path):
    db = tmp_path / "test.db"
    monkeypatch.setattr(database, "DATABASE", str(db))
    database.create_database()
    return db


def test_create_database_makes_tables(monkeypatch, tmp_path):
    _use_temp_db(monkeypatch, tmp_path)

    conn = database.get_connection()
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    conn.close()

    assert "articles" in tables
    assert "searches" in tables
    assert "download_failures" in tables


def test_save_article_insert_and_update(monkeypatch, tmp_path):
    _use_temp_db(monkeypatch, tmp_path)

    database.save_article({
        "pmid": "32033537",
        "pmcid": "PMC32033337",
        "doi": "10.1186/s12859-020-3379-z",
        "title": "In Silico Strategies in Tuberculosis Drug Discovery.",
        "authors": "A; B",
        "journal": "Molecules (Basel, Switzerland)",
        "year": "2020",
        "abstract": "abs",
    })

    row = database.get_article_by_pmid("32033537")
    assert row["title"] == "In Silico Strategies in Tuberculosis Drug Discovery."
    assert row["pmcid"] == "PMC32033337"

    database.save_article({
        "pmid": "32033537",
        "pmcid": None,
        "title": "Updated title",
        "authors": "A",
        "journal": "Nature",
        "year": "2021",
        "abstract": "abs2",
    })

    row = database.get_article_by_pmid("32033537")
    assert row["title"] == "Updated title"
    assert row["pmcid"] == "PMC32033337"
    assert row["publication_year"] == "2021"


def test_full_text_helpers(monkeypatch, tmp_path):
    _use_temp_db(monkeypatch, tmp_path)

    database.save_article({
        "pmid": "222",
        "title": "No text",
        "year": "2019",
    })

    assert database.has_full_text("222") is False

    database.update_full_text("222", "PMC222", "full text")

    assert database.has_full_text("222") is True
    assert database.get_article_by_pmid("222")["full_text"] == "full text"


def test_download_failure_increments(monkeypatch, tmp_path):
    _use_temp_db(monkeypatch, tmp_path)

    database.log_download_failure("333", "PMC333", "oai", "timeout")
    database.log_download_failure("333", "PMC333", "oai", "timeout again")

    fails = database.get_download_failures()
    assert len(fails) == 1
    assert fails[0]["attempt_count"] == 2
    assert "timeout again" in fails[0]["error_message"]

    database.clear_download_failure("333")
    assert database.get_download_failures() == []


def test_search_history(monkeypatch, tmp_path):
    _use_temp_db(monkeypatch, tmp_path)

    sid = database.create_search(
        query="PDE4",
        start_year=2015,
        end_year=2024,
        pmc_only=True,
        pubmed_total=100,
        requested=50,
    )

    database.update_search(sid, retrieved=43, full_text_downloaded=13)

    conn = database.get_connection()
    row = conn.execute(
        "SELECT * FROM searches WHERE id = ?",
        (sid,),
    ).fetchone()
    conn.close()

    query,retrived,dowloaded = row[1],row[7],row[8]

    assert (query,retrived,dowloaded) == ("PDE4",43,13)
  