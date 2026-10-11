"""
Retry logic for full-text downloads.
No real PMC calls here.
"""

from unittest.mock import patch

import corpus


def test_download_succeeds_on_first_try():
    article = {"pmid": "12345", "pmcid": "PMC1"}
    test_sample = {"pmid": "12345", "full_text": "some text"}

    with patch("corpus.download_article", return_value=test_sample) as dl, \
         patch("corpus.time.sleep") as sleep:
        result, attempts, err = corpus.download_with_retry(article)

    assert result == test_sample
    assert attempts == 1
    assert err is None
    assert dl.call_count == 1
    sleep.assert_not_called()


def test_download_recovery_after_failures():
    # first timeout, then empty result, then ok
    article = {"pmid": "12345"}
    test_sample = {"full_text": "ok"}

    with patch(
        "corpus.download_article",
        side_effect=[Exception("timeout"), None, test_sample],
    ) as dl, patch("corpus.time.sleep") as sleep:
        result, attempts, err = corpus.download_with_retry(article)

    assert result == test_sample
    assert attempts == 3
    assert err is None
    assert dl.call_count == 3
    assert sleep.call_count == 2


def test_retry_max_retries():
    article = {"pmid": "999"}

    with patch(
        "corpus.download_article",
        side_effect=Exception("network down"),
    ) as dl, patch("corpus.time.sleep"):
        result, attempts, err = corpus.download_with_retry(article)

    assert result is None
    assert attempts == corpus.MAX_RETRIES
    assert "network down" in err
    assert dl.call_count == corpus.MAX_RETRIES
