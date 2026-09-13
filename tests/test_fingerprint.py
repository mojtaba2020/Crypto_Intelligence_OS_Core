from crypto_intelligence_os.core.fingerprint import error_fingerprint


def test_error_fingerprint_is_stable_and_normalized() -> None:
    left = error_fingerprint("DATA_ERROR", "STALE", "Market")
    right = error_fingerprint(" data_error ", "stale", "market")
    assert left == right
    assert len(left) == 24
