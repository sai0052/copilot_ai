from app.llm.rate_limit import compute_wait_seconds, public_wait_label


def test_retry_after_header_wins():
    assert compute_wait_seconds(retry_after="12", retry_index=0, base_seconds=5) == 12.0


def test_exponential_sequence():
    assert compute_wait_seconds(retry_after=None, retry_index=0, base_seconds=5, jitter=0) == 5.0
    assert compute_wait_seconds(retry_after=None, retry_index=1, base_seconds=5, jitter=0) == 10.0
    assert compute_wait_seconds(retry_after=None, retry_index=2, base_seconds=5, jitter=0) == 20.0


def test_body_try_again_in():
    wait = compute_wait_seconds(retry_after=None, body="Please try again in 7.25s", retry_index=0, base_seconds=5)
    assert wait == 7.25


def test_wait_label():
    assert public_wait_label(12.3) == "Waiting 12 seconds before retry..."
