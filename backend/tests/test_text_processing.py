from app.services.text_processing.cleaning_service import clean_text


def test_multiple_spaces():
    text = "Hello     World"
    assert clean_text(text) == "Hello World"


def test_excessive_newlines():
    text = "Hello\n\n\n\nWorld"
    assert clean_text(text) == "Hello\n\nWorld"


def test_leading_and_trailing_spaces():
    text = "   Hello World   "
    assert clean_text(text) == "Hello World"


def test_line_endings():
    text = "Hello\r\nWorld"
    assert clean_text(text) == "Hello\nWorld"


def test_empty_text():
    assert clean_text("") == ""


def test_none_text():
    assert clean_text(None) == ""


def test_document_structure():
    text = """
    Heading


    This is a paragraph.


    - Item one
    - Item two
    """

    expected = "Heading\n\nThis is a paragraph.\n\n- Item one\n- Item two"

    assert clean_text(text) == expected