"""Ring 2 bootstrap: Embedding generation function tests.

These tests validate get_embedding function with proper mocking of requests to 
Ollama instances. Tests include load balancing, timeout handling, error scenarios,
and intelligent routing across multiple instances. They are NOT yet part of 
enforced coverage gating.

Run standalone (without coverage gate) via:
    pytest tests/test_pdf_processor_embedding.py --no-cov
"""

from unittest.mock import Mock, patch
import requests

import pytest

from pdf_processor.pdf_utils import get_embedding


@pytest.mark.unit
@patch('pdf_processor.pdf_utils.requests.post')
@patch('pdf_processor.pdf_utils.get_settings')
def test_get_embedding_success_first_instance(mock_get_settings, mock_post):
    """Test successful embedding generation from first Ollama instance."""
    # Mock settings
    mock_settings = Mock()
    mock_settings.embedding_model = "nomic-embed-text:v1.5"
    mock_settings.embedding_timeout_seconds = 60
    mock_get_settings.return_value = mock_settings
    
    mock_response = Mock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {
        'embeddings': [[0.1, 0.2, 0.3, 0.4, 0.5]]
    }
    mock_post.return_value = mock_response
    
    result = get_embedding("Test text for embedding")
    
    assert result == [0.1, 0.2, 0.3, 0.4, 0.5]
    mock_post.assert_called_once()
    
    # Check request parameters
    call_args = mock_post.call_args
    assert "ollama-server" in call_args[0][0]  # URL contains ollama-server
    assert call_args[1]['json']['input'] == "Test text for embedding"


@pytest.mark.unit
@patch('pdf_processor.pdf_utils.requests.post')
def test_get_embedding_load_balancing(mock_post):
    """Test load balancing when first instance fails."""
    # First instance fails with connection error
    mock_response_fail = Mock()
    mock_response_fail.raise_for_status.side_effect = requests.exceptions.ConnectionError("Connection failed")
    
    # Second instance succeeds
    mock_response_success = Mock()
    mock_response_success.raise_for_status.return_value = None
    mock_response_success.json.return_value = {
        'embeddings': [[0.6, 0.7, 0.8]]
    }
    
    mock_post.side_effect = [mock_response_fail, mock_response_success]
    
    result = get_embedding("Test text")
    
    assert result == [0.6, 0.7, 0.8]
    assert mock_post.call_count == 2  # Tried first, then second


@pytest.mark.unit
@patch('pdf_processor.pdf_utils.requests.post')
def test_get_embedding_timeout_handling(mock_post):
    """Test timeout handling and retry to next instance."""
    # First instance times out
    mock_post.side_effect = [
        requests.exceptions.Timeout("Request timed out"),
        Mock(raise_for_status=Mock(), json=Mock(return_value={'embeddings': [[0.9, 1.0]]}))
    ]
    
    result = get_embedding("Test text")
    
    assert result == [0.9, 1.0]
    assert mock_post.call_count == 2


@pytest.mark.unit
@patch('pdf_processor.pdf_utils.requests.post')
def test_get_embedding_http_error_retry(mock_post):
    """Test retry on HTTP errors."""
    # First instance returns HTTP error
    mock_response_error = Mock()
    mock_response_error.raise_for_status.side_effect = requests.exceptions.HTTPError("500 Server Error")
    
    # Second instance succeeds
    mock_response_success = Mock()
    mock_response_success.raise_for_status.return_value = None
    mock_response_success.json.return_value = {'embeddings': [[0.1, 0.2]]}
    
    mock_post.side_effect = [mock_response_error, mock_response_success]
    
    result = get_embedding("Test text")
    
    assert result == [0.1, 0.2]
    assert mock_post.call_count == 2


@pytest.mark.unit
@patch('pdf_processor.pdf_utils.requests.post')
def test_get_embedding_all_instances_fail(mock_post):
    """Test behavior when all Ollama instances fail."""
    mock_post.side_effect = requests.exceptions.ConnectionError("All instances down")
    
    with pytest.raises(RuntimeError) as exc_info:
        get_embedding("Test text")
    
    assert "Failed to get embedding from all available Ollama instances" in str(exc_info.value)
    assert mock_post.call_count == 4  # Should try all 4 instances


@pytest.mark.unit
@patch('pdf_processor.pdf_utils.requests.post')
def test_get_embedding_empty_response(mock_post):
    """Test handling of empty embedding response."""
    mock_response = Mock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {'embeddings': []}  # Empty embeddings
    mock_post.return_value = mock_response
    
    with pytest.raises(RuntimeError) as exc_info:
        get_embedding("Test text")
    
    assert "Failed to get embedding" in str(exc_info.value)


@pytest.mark.unit
@patch('pdf_processor.pdf_utils.requests.post')
def test_get_embedding_no_embeddings_key(mock_post):
    """Test handling of response missing embeddings key."""
    mock_response = Mock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {}  # No embeddings key
    mock_post.return_value = mock_response
    
    with pytest.raises(RuntimeError) as exc_info:
        get_embedding("Test text")
    
    assert "Failed to get embedding" in str(exc_info.value)


@pytest.mark.unit
@patch('pdf_processor.pdf_utils.requests.post')
def test_get_embedding_custom_model(mock_post):
    """Test embedding generation with custom model."""
    mock_response = Mock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {'embeddings': [[0.1, 0.2, 0.3]]}
    mock_post.return_value = mock_response
    
    result = get_embedding("Test text", model="custom-embed-model")
    
    assert result == [0.1, 0.2, 0.3]
    
    # Check that custom model was used
    call_args = mock_post.call_args
    assert call_args[1]['json']['model'] == "custom-embed-model"


@pytest.mark.unit
@patch('pdf_processor.pdf_utils.requests.post')
def test_get_embedding_custom_url(mock_post):
    """Test embedding generation with custom Ollama URL."""
    mock_response = Mock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {'embeddings': [[0.4, 0.5, 0.6]]}
    mock_post.return_value = mock_response
    
    custom_url = "http://custom-ollama:11434/api/embed"
    result = get_embedding("Test text", ollama_url=custom_url)
    
    assert result == [0.4, 0.5, 0.6]
    
    # Should only try the custom URL, not load balance
    mock_post.assert_called_once_with(custom_url, json={'model': 'nomic-embed-text:v1.5', 'input': 'Test text'}, timeout=60)


@pytest.mark.unit
@patch('pdf_processor.pdf_utils.requests.post')
def test_get_embedding_long_text(mock_post):
    """Test embedding generation with very long text."""
    long_text = "This is a very long text. " * 1000  # ~26,000 characters
    
    mock_response = Mock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {'embeddings': [[0.7, 0.8, 0.9]]}
    mock_post.return_value = mock_response
    
    result = get_embedding(long_text)
    
    assert result == [0.7, 0.8, 0.9]
    
    # Check that full long text was sent
    call_args = mock_post.call_args
    assert call_args[1]['json']['input'] == long_text
    assert len(call_args[1]['json']['input']) > 25000


@pytest.mark.unit
@patch('pdf_processor.pdf_utils.requests.post')
def test_get_embedding_unicode_text(mock_post):
    """Test embedding generation with Unicode characters."""
    unicode_text = "Héllo wörld! 测试 Тест 🚀 emoji"
    
    mock_response = Mock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {'embeddings': [[0.11, 0.22, 0.33]]}
    mock_post.return_value = mock_response
    
    result = get_embedding(unicode_text)
    
    assert result == [0.11, 0.22, 0.33]
    
    # Check that Unicode text was handled correctly
    call_args = mock_post.call_args
    assert call_args[1]['json']['input'] == unicode_text


@pytest.mark.unit
@patch('pdf_processor.pdf_utils.requests.post')
def test_get_embedding_empty_text(mock_post):
    """Test embedding generation with empty text."""
    mock_response = Mock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {'embeddings': [[0.0, 0.0, 0.0]]}
    mock_post.return_value = mock_response
    
    result = get_embedding("")
    
    assert result == [0.0, 0.0, 0.0]
    
    # Should still make the request with empty string
    call_args = mock_post.call_args
    assert call_args[1]['json']['input'] == ""


@pytest.mark.unit
@patch('pdf_processor.pdf_utils.requests.post')
def test_get_embedding_request_exception(mock_post):
    """Test handling of generic request exceptions."""
    mock_post.side_effect = requests.exceptions.RequestException("Generic request error")
    
    with pytest.raises(RuntimeError) as exc_info:
        get_embedding("Test text")
    
    assert "Failed to get embedding" in str(exc_info.value)
    assert mock_post.call_count == 4  # Should try all instances


@pytest.mark.unit
@patch('pdf_processor.pdf_utils.requests.post')
def test_get_embedding_json_decode_error(mock_post):
    """Test handling of JSON decode errors in response."""
    mock_response = Mock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.side_effect = ValueError("Invalid JSON")
    mock_post.return_value = mock_response
    
    with pytest.raises(RuntimeError) as exc_info:
        get_embedding("Test text")
    
    assert "Failed to get embedding" in str(exc_info.value)


@pytest.mark.unit
@patch('pdf_processor.pdf_utils.requests.post')
def test_get_embedding_partial_success_different_instances(mock_post):
    """Test that different instances are tried in random order."""
    # Mock 3 failures, then 1 success
    mock_post.side_effect = [
        requests.exceptions.ConnectionError("Instance 1 down"),
        requests.exceptions.ConnectionError("Instance 2 down"), 
        requests.exceptions.ConnectionError("Instance 3 down"),
        Mock(raise_for_status=Mock(), json=Mock(return_value={'embeddings': [[0.99]]}))
    ]
    
    result = get_embedding("Test text")
    
    assert result == [0.99]
    assert mock_post.call_count == 4  # Should try all until success


@pytest.mark.unit
@patch('pdf_processor.pdf_utils.requests.post')
def test_get_embedding_large_embedding_dimension(mock_post):
    """Test handling of large embedding vectors."""
    # Simulate a large embedding (e.g., 1536 dimensions)
    large_embedding = [i * 0.001 for i in range(1536)]
    
    mock_response = Mock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {'embeddings': [large_embedding]}
    mock_post.return_value = mock_response
    
    result = get_embedding("Test text")
    
    assert result == large_embedding
    assert len(result) == 1536


@pytest.mark.unit
@patch('pdf_processor.pdf_utils.requests.post')
def test_get_embedding_timeout_configuration(mock_post):
    """Test that timeout is properly configured in requests."""
    mock_response = Mock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {'embeddings': [[0.1, 0.2]]}
    mock_post.return_value = mock_response
    
    get_embedding("Test text")
    
    # Check that timeout parameter was set
    call_args = mock_post.call_args
    assert 'timeout' in call_args[1]
    assert call_args[1]['timeout'] == 60  # Default timeout from settings