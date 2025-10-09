"""Ring 2 bootstrap: PDF extraction function tests (simplified).

These tests validate the core PDF extraction utilities with proper error handling.
They focus on import error scenarios and basic validation without complex mocking.
"""

import pytest
from unittest.mock import patch, Mock

from pdf_processor.pdf_utils import extract_text, extract_tables, extract_images


@pytest.mark.unit
def test_extract_text_import_error():
    """Test extract_text raises RuntimeError when PyMuPDF not available."""
    with patch.dict('sys.modules', {'fitz': None}):
        # Clear any cached imports
        import importlib
        import pdf_processor.pdf_utils
        importlib.reload(pdf_processor.pdf_utils)
        
        with pytest.raises(RuntimeError) as exc_info:
            pdf_processor.pdf_utils.extract_text("/fake/path.pdf")
        assert "PyMuPDF (fitz) is required" in str(exc_info.value)


@pytest.mark.unit
def test_extract_tables_import_error():
    """Test extract_tables raises RuntimeError when camelot not available."""
    with patch.dict('sys.modules', {'camelot': None}):
        # Clear any cached imports
        import importlib
        import pdf_processor.pdf_utils
        importlib.reload(pdf_processor.pdf_utils)
        
        with pytest.raises(RuntimeError) as exc_info:
            pdf_processor.pdf_utils.extract_tables("/fake/path.pdf")
        assert "camelot is required" in str(exc_info.value)


@pytest.mark.unit
def test_extract_images_import_error():
    """Test extract_images raises RuntimeError when PyMuPDF not available."""
    with patch.dict('sys.modules', {'fitz': None}):
        # Clear any cached imports
        import importlib
        import pdf_processor.pdf_utils
        importlib.reload(pdf_processor.pdf_utils)
        
        with pytest.raises(RuntimeError) as exc_info:
            pdf_processor.pdf_utils.extract_images("/fake/path.pdf", "/output")
        assert "PyMuPDF (fitz) is required" in str(exc_info.value)


@pytest.mark.unit
@patch('pdf_processor.pdf_utils.fitz', create=True)
def test_extract_text_with_mock_success(mock_fitz):
    """Test successful text extraction with mocked fitz."""
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
@patch('pdf_processor.pdf_utils.camelot', create=True)
def test_extract_tables_with_mock_success(mock_camelot):
    """Test successful table extraction with mocked camelot."""
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
@patch('builtins.open')
@patch('os.makedirs')
@patch('os.path.exists')
@patch('pdf_processor.pdf_utils.fitz', create=True)
def test_extract_images_with_mock_success(mock_fitz, mock_exists, mock_makedirs, mock_open):
    """Test successful image extraction with mocked dependencies."""
    # Mock output directory handling
    mock_exists.return_value = False
    
    # Mock image data
    mock_base_image = {
        "image": b"fake_image_data",
        "ext": "png"
    }
    
    mock_doc = Mock()
    mock_doc.extract_image.return_value = mock_base_image
    
    # Mock page with one image
    mock_page = Mock()
    mock_page.get_images.return_value = [(123, "fake_xref_data")]
    
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
@patch('pdf_processor.pdf_utils.fitz', create=True)
def test_extract_text_file_error(mock_fitz):
    """Test extract_text handles file opening errors."""
    mock_fitz.open.side_effect = Exception("File not found")
    
    with pytest.raises(Exception) as exc_info:
        extract_text("/fake/missing.pdf")
    
    assert "File not found" in str(exc_info.value)


@pytest.mark.unit
@patch('pdf_processor.pdf_utils.camelot', create=True)
def test_extract_tables_no_tables(mock_camelot):
    """Test table extraction when no tables found."""
    mock_tables = Mock()
    mock_tables.__iter__ = Mock(return_value=iter([]))
    
    mock_camelot.read_pdf.return_value = mock_tables
    
    result = extract_tables("/fake/no_tables.pdf")
    
    assert result == []


@pytest.mark.unit
@patch('os.path.exists')
@patch('pdf_processor.pdf_utils.fitz', create=True)
def test_extract_images_no_images(mock_fitz, mock_exists):
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