"""
Knowledge graph v4.1 – schema + insert helpers.
Uses a temporary sqlite file.
"""

import sqlite3

import pytest

import knowledge_graph_v41 as kg


def _setup(monkeypatch, tmp_path):
    db = tmp_path / "kg.db"
    monkeypatch.setattr(kg, "DATABASE", str(db))

    # mentions/assertions FK to articles, so create a stub
    conn = sqlite3.connect(str(db))
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(
        """
        CREATE TABLE articles (
            id INTEGER PRIMARY KEY,
            pmid TEXT
        )
        """
    )
    conn.execute(
        "INSERT INTO articles (id, pmid) VALUES (1, '999')"
    )
    conn.commit()
    conn.close()

    kg.create_knowledge_graph_tables()
    return db


def test_entity_create_and_reuse(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)

    a = kg.get_or_create_entity("rolipram", "compound")
    b = kg.get_or_create_entity("  rolipram  ", "COMPOUND")

    assert a == b

    with pytest.raises(ValueError):
        kg.get_or_create_entity("Rolipram", "INVALID")

    with pytest.raises(ValueError):
        kg.get_or_create_entity("   ", "GENE")


def test_relation_assertion_activity_chain(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)

    subj = kg.get_or_create_entity("Rolipram", "DRUG")
    obj = kg.get_or_create_entity("PDE4", "PROTEIN")

    rel1 = kg.get_or_create_relation(subj, "inhibits", obj)
    rel2 = kg.get_or_create_relation(subj, "INHIBITS", obj)
    assert rel1 == rel2

    assertion_id = kg.add_assertion(
        relation_id=rel1,
        article_id=1,
        evidence_sentence="Rolipram inhibits PDE4 with IC50 of 12 nM.",
        evidence_type="in_vitro",
        assay="enzyme assay",
        confidence=0.8,
    )

    act_id = kg.add_activity(
        assertion_id=assertion_id,
        activity_type="ic50",
        value=12.0,
        unit="nM",
        raw_value="12 nM",
    )

    assert assertion_id is not None
    assert act_id is not None

    stats = kg.get_statistics()
    assert stats["entities"] == 2
    assert stats["relations"] == 1
    assert stats["assertions"] == 1
    assert stats["activities"] == 1


def test_bad_vocab_raises(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)

    subj = kg.get_or_create_entity("A", "COMPOUND")
    obj = kg.get_or_create_entity("B", "PROTEIN")

    with pytest.raises(ValueError):
        kg.get_or_create_relation(subj, "INVALID RELATION", obj)

    rel = kg.get_or_create_relation(subj, "BINDS_TO", obj)

    with pytest.raises(ValueError):
        kg.add_assertion(
            relation_id=rel,
            article_id=1,
            evidence_sentence="something",
            evidence_type="INVALID EVIDENCE",
        )

    assertion_id = kg.add_assertion(
        relation_id=rel,
        article_id=1,
        evidence_sentence="A binds to B.",
    )

    with pytest.raises(ValueError):
        kg.add_activity(assertion_id, "INVALID ACTIVITY", value=1.0)


def test_add_mention(monkeypatch, tmp_path):
    _setup(monkeypatch, tmp_path)

    eid = kg.get_or_create_entity("PDE4", "GENE")
    mid = kg.add_mention(
        article_id=1,
        entity_id=eid,
        surface_form="phosphodiesterase-4",
        section="results",
        confidence=0.9,
    )

    assert mid is not None
    assert kg.get_statistics()["mentions"] == 1
