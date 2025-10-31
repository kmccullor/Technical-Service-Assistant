"""Ring 2 bootstrap: chunk_text behavior tests.

These tests validate deterministic chunk boundaries, sentence overlap inclusion,
empty input handling, and metadata integrity for the PDF processor's text
chunking utility. They are NOT yet part of enforced coverage gating.
Run standalone (without coverage gate) via:

    pytest -k pdf_processor_chunking -p no:cov
"""

import pytest

from pdf_processor.pdf_utils import chunk_images, chunk_text


@pytest.mark.unit
def test_chunk_text_empty_input():
    chunks, next_index = chunk_text("")
    assert chunks == []
    assert next_index == 0


@pytest.mark.unit
def test_chunk_text_single_sentence():
    text = "This is a single sentence only."
    chunks, next_index = chunk_text(text, document_name="docA")
    assert len(chunks) == 1
    c = chunks[0]
    assert c["text"].strip() == text.strip()
    assert c["metadata"]["document"] == "docA"
    assert next_index == 1


@pytest.mark.unit
def test_chunk_text_multi_paragraph_with_overlap():
    text = (
        "Para one first sentence. Para one second sentence.\n\n"
        "Para two first sentence. Para two second sentence. Para two third sentence."
    )
    chunks, next_index = chunk_text(text, document_name="docB")
    # Expect one chunk per sentence, with each (except first in paragraph) including previous sentence prefix
    sentence_texts = [c["text"] for c in chunks]
    assert any("Para one first sentence." in t for t in sentence_texts)
    # Overlap: second sentence chunk should start with first sentence content
    second_chunk = sentence_texts[1]
    assert second_chunk.startswith("Para one first sentence.")
    # Paragraph boundary: first sentence of paragraph two should not include last sentence of paragraph one
    para_two_first = sentence_texts[2]
    assert not para_two_first.startswith("Para one second sentence.")
    assert next_index == len(chunks)


@pytest.mark.unit
def test_chunk_text_start_index_offset():
    text = "Sentence one. Sentence two."
    chunks, next_idx = chunk_text(text, document_name="docC", start_index=10)
    assert chunks[0]["page_number"] == 10
    assert next_idx == 10 + len(chunks)


@pytest.mark.unit
def test_chunk_images_metadata_integrity():
    img_paths = ["/tmp/imgA.png", "/tmp/imgB.png"]
    chunks, _ = chunk_images(img_paths, document_name="docI3")
    for idx, c in enumerate(chunks):
        md = c["metadata"]
        assert md["document"] == "docI3"
        assert md["type"] == "image"
        assert md["path"] == img_paths[idx]
        assert md["image_index"] == idx


@pytest.mark.unit
def test_chunk_images_long_paths():
    """Test image chunking with very long file paths."""
    long_path = "/" + "/".join(["very_long_directory_name"] * 10) + "/image_with_very_long_filename.png"
    chunks, _ = chunk_images([long_path], document_name="long_path_doc")

    assert len(chunks) == 1
    assert "image_with_very_long_filename.png" in chunks[0]["text"]
    assert chunks[0]["metadata"]["path"] == long_path


@pytest.mark.unit
def test_chunk_images_special_characters_in_paths():
    """Test image chunking with special characters in file paths."""
    special_paths = [
        "/tmp/image with spaces.jpg",
        "/tmp/image-with-dashes.png",
        "/tmp/image_with_underscores.gif",
        "/tmp/image#with#hash.bmp",
    ]
    chunks, _ = chunk_images(special_paths, document_name="special_paths_doc")

    assert len(chunks) == 4
    for i, path in enumerate(special_paths):
        filename = path.split("/")[-1]
        assert filename in chunks[i]["text"]
        assert chunks[i]["metadata"]["path"] == path


@pytest.mark.unit
def test_chunk_images_different_extensions():
    """Test image chunking with various file extensions."""
    img_paths = [
        "/tmp/photo.jpg",
        "/tmp/diagram.png",
        "/tmp/animation.gif",
        "/tmp/icon.bmp",
        "/tmp/vector.svg",
        "/tmp/unknown.xyz",  # Unknown extension
    ]
    chunks, _ = chunk_images(img_paths, document_name="extensions_doc")

    assert len(chunks) == 6
    for i, path in enumerate(img_paths):
        filename = path.split("/")[-1]
        assert filename in chunks[i]["text"]
        assert chunks[i]["metadata"]["image_index"] == i


# --- Edge case tests for chunking ---


@pytest.mark.unit
def test_chunk_text_unicode_handling():
    """Test chunking with Unicode characters."""
    text = "Héllo wörld. Tést sëntence with ñ and ç."
    chunks, next_idx = chunk_text(text, document_name="unicode_doc")
    assert len(chunks) == 2
    assert "Héllo wörld" in chunks[0]["text"]
    assert "Tést sëntence" in chunks[1]["text"]
    assert next_idx == 2


@pytest.mark.unit
def test_chunk_text_very_long_text():
    """Test chunking with very long text."""
    # Create a long paragraph with many sentences
    sentences = [f"This is sentence number {i}." for i in range(50)]
    text = " ".join(sentences)
    chunks, next_idx = chunk_text(text, document_name="long_doc")

    assert len(chunks) == 50
    assert next_idx == 50

    # Check overlap behavior
    for i in range(1, len(chunks)):
        # Each chunk after the first should start with the previous sentence
        assert chunks[i]["text"].startswith(sentences[i - 1])


@pytest.mark.unit
def test_chunk_text_special_characters():
    """Test chunking with special characters and punctuation."""
    text = "Question? Answer! Exclamation... Multiple dots."
    chunks, _ = chunk_text(text, document_name="special_doc")

    # Should recognize different sentence endings
    assert len(chunks) >= 3  # At least 3 different sentence types
    assert any("Question?" in c["text"] for c in chunks)
    assert any("Answer!" in c["text"] for c in chunks)
    assert any("Multiple dots." in c["text"] for c in chunks)


@pytest.mark.unit
def test_chunk_text_empty_paragraphs():
    """Test chunking with multiple empty paragraphs."""
    text = "First paragraph.\n\n\n\nSecond paragraph after multiple newlines."
    chunks, _ = chunk_text(text, document_name="empty_para_doc")

    # Should skip empty paragraphs
    assert len(chunks) == 2
    assert chunks[0]["metadata"]["paragraph"] == 0
    # The second chunk will have paragraph index based on actual paragraph structure
    assert chunks[1]["metadata"]["paragraph"] > chunks[0]["metadata"]["paragraph"]


@pytest.mark.unit
def test_chunk_text_whitespace_only_paragraphs():
    """Test chunking with whitespace-only paragraphs."""
    text = "First paragraph.\n\n   \t  \n\nSecond paragraph."
    chunks, _ = chunk_text(text, document_name="whitespace_doc")

    # Should skip whitespace-only paragraphs
    assert len(chunks) == 2
    assert "First paragraph" in chunks[0]["text"]
    assert "Second paragraph" in chunks[1]["text"]


@pytest.mark.unit
def test_chunk_text_single_word_sentences():
    """Test chunking with very short sentences."""
    text = "Yes. No. Maybe. Definitely not."
    chunks, _ = chunk_text(text, document_name="short_doc")

    assert len(chunks) == 4
    # Check overlap works even with very short sentences
    assert chunks[1]["text"].startswith("Yes.")
    assert chunks[2]["text"].startswith("No.")
    assert chunks[3]["text"].startswith("Maybe.")


@pytest.mark.unit
def test_chunk_text_no_sentence_endings():
    """Test chunking with text that has no clear sentence endings."""
    text = "This is a paragraph without proper sentence endings, just commas and conjunctions"
    chunks, _ = chunk_text(text, document_name="no_endings_doc")

    # NLTK should still create at least one chunk
    assert len(chunks) >= 1
    assert chunks[0]["text"] == text  # Should be treated as one sentenceunks[i]["metadata"]["image_index"] == i
