from app.services.plagiarism_service import preprocess_text


def test_preprocess_text_removes_stopwords():
    text = "This is a simple and clean TEST sentence."
    processed = preprocess_text(text)
    assert "test" in processed
    assert "this" not in processed
    assert "is" not in processed