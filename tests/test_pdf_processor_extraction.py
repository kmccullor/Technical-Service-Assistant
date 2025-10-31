"""Ring 2 bootstrap: PDF extraction function tests.

These tests validate the core PDF extraction utilities (extract_text, extract_tables,
extract_images) with proper mocking of external dependencies. They are NOT yet part
of enforced coverage gating.

Run standalone (without coverage gate) via:
    pytest tests/test_pdf_processor_extraction.py --no-cov
"""

from unittest.mock import Mock, patch

import pytest

from pdf_processor.pdf_utils import extract_images, extract_tables, extract_text


@pytest.mark.unit
def test_extract_text_success():
    """Test successful text extraction from PDF."""
    with patch.dict("sys.modules", {"fitz": Mock()}) as mock_modules:
        mock_fitz = mock_modules["fitz"]

        # Mock PyMuPDF document
        mock_page = Mock()
        mock_page.get_text.return_value = "Page 1 content"

        mock_doc = Mock()
        mock_doc.__len__ = Mock(return_value=1)
        mock_doc.__getitem__ = Mock(return_value=mock_page)
        mock_doc.close = Mock()

        mock_fitz.open.return_value = mock_doc

        result = extract_text("/fake/path.pdf")

        assert result == "Page 1 content"
        mock_fitz.open.assert_called_once_with("/fake/path.pdf")
        mock_page.get_text.assert_called_once()
        mock_doc.close.assert_called_once()


@pytest.mark.unit
@patch("pdf_processor.pdf_utils.fitz")
def test_extract_text_multiple_pages(mock_fitz):
    """Test text extraction from multi-page PDF."""
    mock_pages = [Mock(), Mock()]
    mock_pages[0].get_text.return_value = "Page 1 text"
    mock_pages[1].get_text.return_value = "Page 2 text"

    mock_doc = Mock()
    mock_doc.__len__ = Mock(return_value=2)
    mock_doc.__getitem__ = Mock(side_effect=lambda i: mock_pages[i])
    mock_doc.close = Mock()

    mock_fitz.open.return_value = mock_doc

    result = extract_text("/fake/multi.pdf")

    assert result == "Page 1 textPage 2 text"
    assert mock_pages[0].get_text.call_count == 1
    assert mock_pages[1].get_text.call_count == 1


@pytest.mark.unit
@patch("pdf_processor.pdf_utils.fitz")
def test_extract_text_empty_pages(mock_fitz):
    """Test text extraction from PDF with empty pages."""
    mock_page = Mock()
    mock_page.get_text.return_value = ""

    mock_doc = Mock()
    mock_doc.__len__ = Mock(return_value=1)
    mock_doc.__getitem__ = Mock(return_value=mock_page)
    mock_doc.close = Mock()

    mock_fitz.open.return_value = mock_doc

    result = extract_text("/fake/empty.pdf")

    assert result == ""


@pytest.mark.unit
def test_extract_text_import_error():
    """Test extract_text raises RuntimeError when PyMuPDF not available."""
    with patch.dict("sys.modules", {"fitz": None}):
        with pytest.raises(RuntimeError) as exc_info:
            extract_text("/fake/path.pdf")
        assert "PyMuPDF (fitz) is required" in str(exc_info.value)


@pytest.mark.unit
@patch("pdf_processor.pdf_utils.fitz")
def test_extract_text_file_error(mock_fitz):
    """Test extract_text handles file opening errors."""
    mock_fitz.open.side_effect = Exception("File not found")

    with pytest.raises(Exception) as exc_info:
        extract_text("/fake/missing.pdf")

    assert "File not found" in str(exc_info.value)


# --- Table extraction tests ---


@pytest.mark.unit
@patch("pdf_processor.pdf_utils.camelot")
def test_extract_tables_success(mock_camelot):
    """Test successful table extraction from PDF."""
    # Mock camelot table with DataFrame
    mock_df = Mock()
    mock_df.to_dict.return_value = [{"col1": "A", "col2": "B"}]

    mock_table = Mock()
    mock_table.df = mock_df

    mock_tables = Mock()
    mock_tables.__iter__ = Mock(return_value=iter([mock_table]))

    mock_camelot.read_pdf.return_value = mock_tables

    result = extract_tables("/fake/tables.pdf")

    assert result == [[{"col1": "A", "col2": "B"}]]
    mock_camelot.read_pdf.assert_called_once_with("/fake/tables.pdf", pages="all")
    mock_df.to_dict.assert_called_once_with("records")


@pytest.mark.unit
@patch("pdf_processor.pdf_utils.camelot")
def test_extract_tables_multiple_tables(mock_camelot):
    """Test extraction of multiple tables from PDF."""
    # Mock two tables
    mock_df1 = Mock()
    mock_df1.to_dict.return_value = [{"a": 1}]
    mock_table1 = Mock()
    mock_table1.df = mock_df1

    mock_df2 = Mock()
    mock_df2.to_dict.return_value = [{"b": 2}, {"b": 3}]
    mock_table2 = Mock()
    mock_table2.df = mock_df2

    mock_tables = Mock()
    mock_tables.__iter__ = Mock(return_value=iter([mock_table1, mock_table2]))

    mock_camelot.read_pdf.return_value = mock_tables

    result = extract_tables("/fake/multi_tables.pdf")

    assert len(result) == 2
    assert result[0] == [{"a": 1}]
    assert result[1] == [{"b": 2}, {"b": 3}]


@pytest.mark.unit
@patch("pdf_processor.pdf_utils.camelot")
def test_extract_tables_no_tables(mock_camelot):
    """Test table extraction when no tables found."""
    mock_tables = Mock()
    mock_tables.__iter__ = Mock(return_value=iter([]))

    mock_camelot.read_pdf.return_value = mock_tables

    result = extract_tables("/fake/no_tables.pdf")

    assert result == []


@pytest.mark.unit
def test_extract_tables_import_error():
    """Test extract_tables raises RuntimeError when camelot not available."""
    with patch.dict("sys.modules", {"camelot": None}):
        with pytest.raises(RuntimeError) as exc_info:
            extract_tables("/fake/path.pdf")
        assert "camelot is required" in str(exc_info.value)


# --- Image extraction tests ---


@pytest.mark.unit
@patch("pdf_processor.pdf_utils.fitz")
@patch("os.path.exists")
@patch("os.makedirs")
@patch("builtins.open")
def test_extract_images_success(mock_open, mock_makedirs, mock_exists, mock_fitz):
    """Test successful image extraction from PDF."""
    # Mock output directory
    mock_exists.return_value = False

    # Mock image data
    mock_base_image = {"image": b"fake_image_data", "ext": "png"}

    mock_doc = Mock()
    mock_doc.extract_image.return_value = mock_base_image

    # Mock page with one image
    mock_page = Mock()
    mock_page.get_images.return_value = [(123, "fake_xref_data")]  # xref, additional data

    mock_doc.__len__ = Mock(return_value=1)
    mock_doc.load_page.return_value = mock_page

    mock_fitz.open.return_value = mock_doc

    # Mock file writing
    mock_file = Mock()
    mock_open.return_value.__enter__ = Mock(return_value=mock_file)
    mock_open.return_value.__exit__ = Mock(return_value=False)

    result = extract_images("/fake/doc.pdf", "/tmp/output")

    assert len(result) == 1
    assert result[0] == "/tmp/output/doc_page1_img1.png"

    mock_makedirs.assert_called_once_with("/tmp/output", exist_ok=True)
    mock_page.get_images.assert_called_once_with(full=True)
    mock_doc.extract_image.assert_called_once_with(123)
    mock_file.write.assert_called_once_with(b"fake_image_data")


@pytest.mark.unit
@patch("pdf_processor.pdf_utils.fitz")
@patch("os.path.exists")
@patch("os.makedirs")
@patch("builtins.open")
def test_extract_images_multiple_pages_images(mock_open, mock_makedirs, mock_exists, mock_fitz):
    """Test image extraction from multiple pages with multiple images."""
    mock_exists.return_value = True  # Directory exists

    # Mock image data
    mock_base_image = {"image": b"image_bytes", "ext": "jpg"}

    mock_doc = Mock()
    mock_doc.extract_image.return_value = mock_base_image

    # Mock two pages, each with one image
    mock_page1 = Mock()
    mock_page1.get_images.return_value = [(1, "data1")]

    mock_page2 = Mock()
    mock_page2.get_images.return_value = [(2, "data2")]

    mock_doc.__len__ = Mock(return_value=2)
    mock_doc.load_page.side_effect = [mock_page1, mock_page2]

    mock_fitz.open.return_value = mock_doc

    # Mock file writing
    mock_file = Mock()
    mock_open.return_value.__enter__ = Mock(return_value=mock_file)
    mock_open.return_value.__exit__ = Mock(return_value=False)

    result = extract_images("/path/test.pdf", "/output")

    assert len(result) == 2
    assert result[0] == "/output/test_page1_img1.jpg"
    assert result[1] == "/output/test_page2_img1.jpg"

    # makedirs should not be called since directory exists
    mock_makedirs.assert_not_called()


@pytest.mark.unit
@patch("pdf_processor.pdf_utils.fitz")
@patch("os.path.exists")
def test_extract_images_no_images(mock_exists, mock_fitz):
    """Test image extraction when PDF has no images."""
    mock_exists.return_value = True

    mock_page = Mock()
    mock_page.get_images.return_value = []  # No images

    mock_doc = Mock()
    mock_doc.__len__ = Mock(return_value=1)
    mock_doc.load_page.return_value = mock_page

    mock_fitz.open.return_value = mock_doc

    result = extract_images("/fake/no_images.pdf", "/output")

    assert result == []


@pytest.mark.unit
def test_extract_images_import_error():
    """Test extract_images raises RuntimeError when PyMuPDF not available."""
    with patch.dict("sys.modules", {"fitz": None}):
        with pytest.raises(RuntimeError) as exc_info:
            extract_images("/fake/path.pdf", "/output")
        assert "PyMuPDF (fitz) is required" in str(exc_info.value)


@pytest.mark.unit
@patch("pdf_processor.pdf_utils.fitz")
@patch("os.path.exists")
@patch("os.makedirs")
@patch("builtins.open")
def test_extract_images_default_extension(mock_open, mock_makedirs, mock_exists, mock_fitz):
    """Test image extraction with default extension when ext not provided."""
    mock_exists.return_value = False

    # Mock image data without ext
    mock_base_image = {
        "image": b"image_data"
        # No "ext" key - should default to "png"
    }

    mock_doc = Mock()
    mock_doc.extract_image.return_value = mock_base_image

    mock_page = Mock()
    mock_page.get_images.return_value = [(456, "data")]

    mock_doc.__len__ = Mock(return_value=1)
    mock_doc.load_page.return_value = mock_page

    mock_fitz.open.return_value = mock_doc

    mock_file = Mock()
    mock_open.return_value.__enter__ = Mock(return_value=mock_file)
    mock_open.return_value.__exit__ = Mock(return_value=False)

    result = extract_images("/fake/doc.pdf", "/output")

    assert len(result) == 1
    assert result[0].endswith(".png")  # Should default to PNG
