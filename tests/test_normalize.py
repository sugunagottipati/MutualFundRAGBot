from ingestion.normalize import normalize_document_text


def test_normalize_preserves_headers_and_rewrites_labels() -> None:
    text = """
    ## Fund Details
    Expense   Ratio : 1.2%
    min sip : 100
    min sip : 100
    """

    normalized = normalize_document_text(text)
    lines = normalized.splitlines()

    assert lines[0] == "## Fund Details"
    assert "expense ratio" in lines[1].lower()
    assert "minimum sip" in lines[2].lower()
    assert len(lines) == 3
