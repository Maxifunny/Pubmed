"""
Testing synchronization and retry for failded articles.
"""

import sqlite3
from pathlib import Path

import database
import retry_failures
import sync_database


def test_get_failed_articles_filters(monkeypatch, tmp_path):
    db = tmp_path / "retry.db"
    monkeypatch.setattr(retry_failures, "DATABASE", str(db))
    monkeypatch.setattr(database, "DATABASE", str(db))
    database.create_database()

    database.save_article({
        "pmid": "1",
        "pmcid": "PMC1",
        "title": "has failure, no text",
        "year": "2020",
    })
    database.save_article({
        "pmid": "2",
        "pmcid": "PMC2",
        "title": "already has text",
        "year": "2020",
    })
    database.save_article({
        "pmid": "3",
        "pmcid": None,
        "title": "no pmcid",
        "year": "2020",
    })

    database.update_full_text("2", "PMC2", "full text here")
    database.log_download_failure("1", "PMC1", "oai", "fail")
    database.log_download_failure("2", "PMC2", "oai", "old fail")
    database.log_download_failure("3", None, "oai", "fail")

    rows = retry_failures.get_failed_articles()
    pmids = {r["pmid"] for r in rows}

    # only #1: has pmcid, no full text, and a failure row
    assert pmids == {"1"}


def test_sync_database_updates_from_files(monkeypatch, tmp_path, capsys):
    db = tmp_path / "sync.db"
    articles_dir = tmp_path / "articles"

    monkeypatch.setattr(sync_database, "DATABASE", str(db))
    monkeypatch.setattr(sync_database, "ARTICLES_DIR", articles_dir)
    monkeypatch.setattr(database, "DATABASE", str(db))
    database.create_database()

    database.save_article({
        "pmid": "10",
        "pmcid": "PMC10",
        "title": "sync me",
        "year": "2021",
    })

    pmc_dir = articles_dir / "PMC10"
    pmc_dir.mkdir(parents=True)
    (pmc_dir / "article.txt").write_text(
        "Synced full text content.",
        encoding="utf-8",
    )

    # empty file + unknown pmc folder
    empty_dir = articles_dir / "PMC99"
    empty_dir.mkdir()
    (empty_dir / "article.txt").write_text("   ", encoding="utf-8")

    unknown = articles_dir / "PMC404"
    unknown.mkdir()
    (unknown / "article.txt").write_text("orphan", encoding="utf-8")

    sync_database.sync_database()

    row = database.get_article_by_pmid("10")
    assert row["full_text"] == "Synced full text content."

    out = capsys.readouterr().out
    assert "Updated:   1" in out
    assert "Empty:     1" in out
    assert "Not found: 1" in out
