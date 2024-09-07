import requests
from bs4 import BeautifulSoup
from unittest.mock import patch, Mock
from app.components import request_handler


@patch('requests.get')
@patch('time.sleep')
@patch('app.components.request_handler.log')
def test_get_with_retry_success(mock_log, mock_sleep, mock_get):
    # Arrange: Simulate a successful response
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.content = b"<html><body>Success</body></html>"
    mock_get.return_value = mock_response

    # Act
    result = request_handler.get_with_retry("http://example.com", config={'proxies': []})

    # Assert
    assert result is not None
    assert isinstance(result, BeautifulSoup)
    mock_get.assert_called_once_with("http://example.com", headers=None, timeout=10)
    assert any(f"Sleeping for " in str(call) for call in mock_log.info.call_args_list)
    mock_sleep.assert_called()


@patch('requests.get')
@patch('time.sleep')
@patch('app.components.request_handler.log')
def test_get_with_retry_http_429(mock_log, mock_sleep, mock_get):
    # Arrange: Simulate an HTTP 429 response followed by a successful response
    mock_response_429 = Mock()
    mock_response_429.status_code = 429
    mock_response_success = Mock()
    mock_response_success.status_code = 200
    mock_response_success.content = b"<html><body>Success</body></html>"
    mock_get.side_effect = [mock_response_429, mock_response_success]

    # Act
    result = request_handler.get_with_retry("http://example.com", config={'proxies': []})

    # Assert
    assert result is not None
    assert isinstance(result, BeautifulSoup)
    assert mock_get.call_count == 2
    assert any(f"Too many requests for http://example.com, retrying in " in str(call) for call in mock_log.info.call_args_list)
    assert any(f"Sleeping for " in str(call) for call in mock_log.info.call_args_list)
    assert mock_sleep.call_count == 2


@patch('requests.get')
@patch('time.sleep')
@patch('app.components.request_handler.log')
def test_get_with_retry_request_exception(mock_log, mock_sleep, mock_get):
    # Arrange: Simulate a RequestException followed by a successful response
    mock_get.side_effect = [requests.exceptions.RequestException,
                            Mock(status_code=200, content=b"<html><body>Success</body></html>")]

    # Act
    result = request_handler.get_with_retry("http://example.com", config={'proxies': []})

    # Assert
    assert result is not None
    assert isinstance(result, BeautifulSoup)
    assert mock_get.call_count == 2
    assert any(f"Request failed for http://example.com due to " in str(call) for call in mock_log.info.call_args_list)
    assert any(f"Sleeping for " in str(call) for call in mock_log.info.call_args_list)
    assert mock_sleep.call_count == 2


@patch('requests.get')
@patch('time.sleep')
@patch('app.components.request_handler.log')
def test_get_with_retry_max_retries_exceeded(mock_log, mock_sleep, mock_get):
    # Arrange: Simulate repeated request exceptions
    mock_get.side_effect = requests.exceptions.RequestException

    # Act
    result = request_handler.get_with_retry("http://example.com", config={'proxies': []}, max_retries=3)

    # Assert
    assert result is None
    assert mock_get.call_count == 3
    assert all(f"Request failed for http://example.com due to " in str(call) for call in mock_log.info.call_args_list)
    assert mock_sleep.call_count == 3
