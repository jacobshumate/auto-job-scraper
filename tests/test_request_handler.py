import requests
from unittest.mock import patch, Mock
from app.components import request_handler


@patch('app.components.request_handler.make_request')
@patch('time.sleep')
@patch('app.components.request_handler.log')
def test_get_with_retry_success(mock_log, mock_sleep, mock_get):
    # Simulate a successful response
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.content = b"<html><body>Success</body></html>"
    mock_get.return_value = mock_response

    result = request_handler.get_with_retry("http://example.com")

    assert result.content.decode('utf-8') == '<html><body>Success</body></html>'
    mock_get.assert_called_once_with("http://example.com", None, timeout=10)
    assert any(f"Sleeping for " in str(call) for call in mock_log.debug.call_args_list)
    mock_sleep.assert_called()


@patch('app.components.request_handler.make_request')
@patch('time.sleep')
@patch('app.components.request_handler.log')
def test_get_with_retry_http_429(mock_log, mock_sleep, mock_get):
    # Simulate an HTTP 429 response followed by a successful response
    mock_response_429 = Mock()
    mock_response_429.status_code = 429
    mock_response_success = Mock()
    mock_response_success.status_code = 200
    mock_response_success.content = b"<html><body>Success</body></html>"
    mock_get.side_effect = [mock_response_429, mock_response_success]

    result = request_handler.get_with_retry("http://example.com")

    assert result is not None
    assert mock_get.call_count == 2
    assert any(f"Too many requests for http://example.com, retrying in " in str(call) for call in mock_log.info.call_args_list)
    assert any(f"Sleeping for " in str(call) for call in mock_log.debug.call_args_list)
    assert mock_sleep.call_count == 2


@patch('app.components.request_handler.make_request')
@patch('time.sleep')
@patch('app.components.request_handler.log')
def test_get_with_retry_request_exception(mock_log, mock_sleep, mock_get):
    # Simulate a RequestException followed by a successful response
    mock_get.side_effect = [requests.exceptions.RequestException,
                            Mock(status_code=200, content=b"<html><body>Success</body></html>")]

    result = request_handler.get_with_retry("http://example.com")

    assert result is not None
    assert mock_get.call_count == 2
    assert any(f"Request failed for http://example.com due to " in str(call) for call in mock_log.info.call_args_list)
    assert any(f"Sleeping for " in str(call) for call in mock_log.debug.call_args_list)
    assert mock_sleep.call_count == 2


@patch('app.components.request_handler.make_request')
@patch('time.sleep')
@patch('app.components.request_handler.log')
def test_get_with_retry_max_retries_exceeded(mock_log, mock_sleep, mock_get):
    # Simulate repeated request exceptions
    mock_get.side_effect = requests.exceptions.RequestException

    result = request_handler.get_with_retry("http://example.com", max_retries=3)

    assert result is None
    assert mock_get.call_count == 3
    assert all(f"Request failed for http://example.com due to " in str(call) for call in mock_log.info.call_args_list)
    assert mock_sleep.call_count == 3
