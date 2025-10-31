"""Ring 2 bootstrap: AI classification function tests.

These tests validate AI-powered document classification functions including
classify_document_with_ai, get_ai_classification, parse_ai_classification_response,
and classify_document_fallback. They mock HTTP requests to Ollama instances and
test intelligent routing. They are NOT yet part of enforced coverage gating.

Run standalone (without coverage gate) via:
    pytest tests/test_pdf_processor_ai_classification.py --no-cov
"""

from unittest.mock import Mock, patch

import pytest
import requests

from pdf_processor.pdf_utils import (
    classify_document_fallback,
    classify_document_with_ai,
    get_ai_classification,
    parse_ai_classification_response,
)


@pytest.mark.unit
@patch("pdf_processor.pdf_utils.get_ai_classification")
def test_classify_document_with_ai_success(mock_get_ai):
    """Test successful AI classification."""
    mock_classification = {
        "document_type": "user_guide",
        "product_name": "RNI",
        "product_version": "4.16",
        "document_category": "documentation",
        "confidence": 0.95,
    }
    mock_get_ai.return_value = mock_classification

    text = "RNI 4.16 User Guide for system administration"
    filename = "RNI_4.16_User_Guide.pdf"

    result = classify_document_with_ai(text, filename)

    assert result == mock_classification
    mock_get_ai.assert_called_once()


@pytest.mark.unit
@patch("pdf_processor.pdf_utils.get_ai_classification")
@patch("pdf_processor.pdf_utils.classify_document_fallback")
def test_classify_document_with_ai_fallback_on_failure(mock_fallback, mock_get_ai):
    """Test fallback to rule-based classification when AI fails."""
    mock_get_ai.return_value = None  # AI classification failed

    mock_fallback_result = {
        "document_type": "user_guide",
        "product_name": "RNI",
        "product_version": "4.16",
        "document_category": "guide",
        "confidence": 0.7,
        "metadata": {"classification_method": "rule_based_fallback"},
    }
    mock_fallback.return_value = mock_fallback_result

    result = classify_document_with_ai("Test content", "RNI_Guide.pdf")

    assert result == mock_fallback_result
    mock_get_ai.assert_called_once()
    mock_fallback.assert_called_once_with("Test content", "RNI_Guide.pdf")


@pytest.mark.unit
@patch("pdf_processor.pdf_utils.get_ai_classification")
@patch("pdf_processor.pdf_utils.classify_document_fallback")
def test_classify_document_with_ai_exception_fallback(mock_fallback, mock_get_ai):
    """Test fallback when AI classification raises exception."""
    mock_get_ai.side_effect = Exception("AI service unavailable")

    mock_fallback_result = {
        "document_type": "unknown",
        "product_name": "unknown",
        "product_version": "unknown",
        "document_category": "documentation",
        "confidence": 0.5,
        "metadata": {"classification_method": "rule_based_fallback"},
    }
    mock_fallback.return_value = mock_fallback_result

    result = classify_document_with_ai("Content", "doc.pdf")

    assert result == mock_fallback_result
    mock_fallback.assert_called_once()


@pytest.mark.unit
def test_classify_document_with_ai_empty_text():
    """Test classification with empty text input."""
    result = classify_document_with_ai("", "empty.pdf")

    expected = {
        "document_type": "unknown",
        "product_name": "unknown",
        "product_version": "unknown",
        "document_category": "documentation",
        "confidence": 0.0,
        "metadata": {},
    }

    assert result == expected


@pytest.mark.unit
def test_classify_document_with_ai_whitespace_text():
    """Test classification with whitespace-only text."""
    result = classify_document_with_ai("   \n\t   ", "whitespace.pdf")

    expected = {
        "document_type": "unknown",
        "product_name": "unknown",
        "product_version": "unknown",
        "document_category": "documentation",
        "confidence": 0.0,
        "metadata": {},
    }

    assert result == expected


# --- get_ai_classification tests ---


@pytest.mark.unit
@patch("pdf_processor.pdf_utils.requests.post")
@patch("pdf_processor.pdf_utils.parse_ai_classification_response")
@patch("pdf_processor.pdf_utils.get_settings")
def test_get_ai_classification_success(mock_get_settings, mock_parse, mock_post):
    """Test successful AI classification request."""
    # Mock settings
    mock_settings = Mock()
    mock_settings.chat_model = "mistral:7b"
    mock_settings.embedding_timeout_seconds = 60
    mock_get_settings.return_value = mock_settings

    mock_response = Mock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {"response": '{"document_type": "user_guide", "confidence": 0.9}'}
    mock_post.return_value = mock_response

    mock_parse.return_value = {"document_type": "user_guide", "confidence": 0.9}

    result = get_ai_classification("Test prompt")

    assert result == {"document_type": "user_guide", "confidence": 0.9}
    mock_post.assert_called_once()
    mock_parse.assert_called_once_with('{"document_type": "user_guide", "confidence": 0.9}')


@pytest.mark.unit
@patch("pdf_processor.pdf_utils.requests.post")
@patch("pdf_processor.pdf_utils.get_settings")
def test_get_ai_classification_load_balancing(mock_get_settings, mock_post):
    """Test load balancing across multiple Ollama instances."""
    # Mock settings
    mock_settings = Mock()
    mock_settings.chat_model = "mistral:7b"
    mock_settings.embedding_timeout_seconds = 60
    mock_get_settings.return_value = mock_settings

    # First instance fails, second succeeds
    mock_response_fail = Mock()
    mock_response_fail.raise_for_status.side_effect = requests.exceptions.ConnectionError("Connection failed")

    mock_response_success = Mock()
    mock_response_success.raise_for_status.return_value = None
    mock_response_success.json.return_value = {"response": '{"document_type": "guide"}'}

    mock_post.side_effect = [mock_response_fail, mock_response_success]

    with patch("pdf_processor.pdf_utils.parse_ai_classification_response") as mock_parse:
        mock_parse.return_value = {"document_type": "guide"}

        result = get_ai_classification("Test prompt")

        assert result == {"document_type": "guide"}
        assert mock_post.call_count == 2  # First failed, second succeeded


@pytest.mark.unit
@patch("pdf_processor.pdf_utils.requests.post")
@patch("pdf_processor.pdf_utils.get_settings")
def test_get_ai_classification_all_instances_fail(mock_get_settings, mock_post):
    """Test behavior when all Ollama instances fail."""
    # Mock settings
    mock_settings = Mock()
    mock_settings.chat_model = "mistral:7b"
    mock_settings.embedding_timeout_seconds = 60
    mock_get_settings.return_value = mock_settings

    mock_post.side_effect = requests.exceptions.ConnectionError("All instances down")

    result = get_ai_classification("Test prompt")

    assert result is None
    assert mock_post.call_count == 4  # Should try all 4 instances


@pytest.mark.unit
@patch("pdf_processor.pdf_utils.requests.post")
def test_get_ai_classification_timeout(mock_post):
    """Test handling of request timeouts."""
    mock_post.side_effect = requests.exceptions.Timeout("Request timed out")

    result = get_ai_classification("Test prompt")

    assert result is None


@pytest.mark.unit
@patch("pdf_processor.pdf_utils.requests.post")
def test_get_ai_classification_http_error(mock_post):
    """Test handling of HTTP errors."""
    mock_response = Mock()
    mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("500 Server Error")
    mock_post.return_value = mock_response

    result = get_ai_classification("Test prompt")

    assert result is None


@pytest.mark.unit
@patch("pdf_processor.pdf_utils.requests.post")
def test_get_ai_classification_invalid_response_format(mock_post):
    """Test handling of invalid response format."""
    mock_response = Mock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {}  # No 'response' key
    mock_post.return_value = mock_response

    result = get_ai_classification("Test prompt")

    assert result is None


# --- parse_ai_classification_response tests ---


@pytest.mark.unit
def test_parse_ai_classification_response_valid_json():
    """Test parsing valid JSON response."""
    response = '{"document_type": "user_guide", "product_name": "RNI", "confidence": 0.95}'

    result = parse_ai_classification_response(response)

    expected = {"document_type": "user_guide", "product_name": "RNI", "confidence": 0.95}
    assert result == expected


@pytest.mark.unit
def test_parse_ai_classification_response_json_in_text():
    """Test extracting JSON from text response."""
    response = """Here is the classification:
    {"document_type": "installation_guide", "confidence": 0.8}
    That's my analysis."""

    result = parse_ai_classification_response(response)

    expected = {"document_type": "installation_guide", "confidence": 0.8}
    assert result == expected


@pytest.mark.unit
def test_parse_ai_classification_response_multiline_json():
    """Test parsing multiline JSON response."""
    response = """Classification result:
{
    "document_type": "reference_manual",
    "product_name": "FlexNet",
    "confidence": 0.85
}
End of response."""

    result = parse_ai_classification_response(response)

    expected = {"document_type": "reference_manual", "product_name": "FlexNet", "confidence": 0.85}
    assert result == expected


@pytest.mark.unit
def test_parse_ai_classification_response_invalid_json():
    """Test handling of invalid JSON."""
    response = '{"document_type": "guide", invalid json'

    result = parse_ai_classification_response(response)

    assert result is None


@pytest.mark.unit
def test_parse_ai_classification_response_no_json():
    """Test handling of response with no JSON."""
    response = "This is just plain text with no JSON structure."

    result = parse_ai_classification_response(response)

    assert result is None


@pytest.mark.unit
def test_parse_ai_classification_response_empty():
    """Test handling of empty response."""
    result = parse_ai_classification_response("")

    assert result is None


# --- classify_document_fallback tests ---


@pytest.mark.unit
def test_classify_document_fallback_rni_guide():
    """Test fallback classification for RNI user guide."""
    text = "RNI system administration and configuration"
    filename = "RNI 4.16 User Guide.pdf"

    result = classify_document_fallback(text, filename)

    assert result["document_type"] == "user_guide"
    assert result["product_name"] == "RNI"
    assert result["product_version"] == "4.16"
    assert result["document_category"] == "guide"
    assert result["confidence"] >= 0.7  # Should be high confidence
    assert result["metadata"]["classification_method"] == "rule_based_fallback"


@pytest.mark.unit
def test_classify_document_fallback_installation_guide():
    """Test fallback classification for installation guide."""
    text = "Installation and setup procedures"
    filename = "FlexNet 5.2 Installation Guide.pdf"

    result = classify_document_fallback(text, filename)

    assert result["document_type"] == "installation_guide"
    assert result["product_name"] == "FLEXNET"
    assert result["product_version"] == "5.2"
    assert result["document_category"] == "guide"


@pytest.mark.unit
def test_classify_document_fallback_release_notes():
    """Test fallback classification for release notes."""
    text = "New features and bug fixes in this release"
    filename = "ESM 3.1 Release Notes.pdf"

    result = classify_document_fallback(text, filename)

    assert result["document_type"] == "release_notes"
    assert result["product_name"] == "ESM"
    assert result["product_version"] == "3.1"
    assert result["document_category"] == "notes"


@pytest.mark.unit
def test_classify_document_fallback_security_guide():
    """Test fallback classification for security guide."""
    text = "Security configuration and best practices"
    filename = "MultiSpeak Security Guide.pdf"

    result = classify_document_fallback(text, filename)

    assert result["document_type"] == "security_guide"
    assert result["document_category"] == "administration"


@pytest.mark.unit
def test_classify_document_fallback_unknown_document():
    """Test fallback classification for unknown document type."""
    text = "Some generic content"
    filename = "unknown_document.pdf"

    result = classify_document_fallback(text, filename)

    assert result["document_type"] == "unknown"
    assert result["product_name"] == "unknown"
    assert result["product_version"] == "unknown"
    assert result["document_category"] == "documentation"
    assert result["confidence"] == 0.5  # Default confidence


@pytest.mark.unit
def test_classify_document_fallback_key_topics_extraction():
    """Test extraction of key topics from content."""
    text = """This document covers security encryption authentication
    and installation setup configuration procedures for network communication."""
    filename = "technical_doc.pdf"

    result = classify_document_fallback(text, filename)

    key_topics = result["metadata"]["key_topics"]
    assert "security" in key_topics
    assert "installation" in key_topics
    assert "networking" in key_topics
    assert len(key_topics) <= 5  # Should limit to top 5


@pytest.mark.unit
def test_classify_document_fallback_version_patterns():
    """Test various version number extraction patterns."""
    test_cases = [
        ("Product 1.2.3 Guide.pdf", "1.2.3"),
        ("RNI 4.16 Manual.pdf", "4.16"),
        ("FlexNet 10.0 Docs.pdf", "10.0"),
        ("No Version Doc.pdf", "unknown"),
    ]

    for filename, expected_version in test_cases:
        result = classify_document_fallback("content", filename)
        assert result["product_version"] == expected_version
