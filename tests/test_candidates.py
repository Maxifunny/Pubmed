"""
Candidate sentence scoring for KG v4.1 pilot.
"""

from extract_candidates_v41 import (
    split_sentences,
    classify_sentence,
    extract_candidates,
    ACTIVITY_PATTERN,
    VALUE_PATTERN,
)


def test_split_sentences_basic():
    text = (
        "This is the first sentence about a drug. "
        "Another sentence. this should also be kept. "
        "Too short."
    )

    sents = split_sentences(text)

    assert len(sents) == 2
    assert "first sentence" in sents[0]


def test_activity_and_value_patterns():
    s = "The compound showed an IC50 of 12 mM."

    assert ACTIVITY_PATTERN.search(s)
    assert VALUE_PATTERN.search(s)

    m = VALUE_PATTERN.search(s)
    assert "12" in m.group(1)
    assert m.group(2).lower() in {"mm"}


def test_classify_sentence_scores():
    plain = "The cells have not incubated in last 15 minutes."
    assert classify_sentence(plain)["score"] == 0

    with_rel = (
        "Rolipram inhibits PDE4 activity in this model."
    )
    c = classify_sentence(with_rel)
    assert c["relation"] is True
    assert c["score"] >= 2

    with_val = (
        "Compound X showed EC50 of 14 nM against the target"
    )
    c = classify_sentence(with_val)
    assert c["activity"] and c["quantitative"]
    # activity(+3) + quantitative(+4) at least
    assert c["score"] >= 7


def test_extract_candidates_filters_and_sorts():
    text = (
        "This sentence has no pharmacological signal at all. "
        "Rolipram inhibits PDE4. "
        "The measured IC50 of 12 nM confirms."
    )

    sentences, candidates = extract_candidates(text)

    assert len(sentences) >= 2
    assert all(c["score"] > 0 for c in candidates)

    # strongest candidate first
    scores = [c["score"] for c in candidates]
    assert scores == sorted(scores, reverse=True)
    assert "IC50" in candidates[0]["sentence"]
