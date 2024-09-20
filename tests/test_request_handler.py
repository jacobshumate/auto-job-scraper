import json
import requests
from unittest.mock import patch, Mock
from app.components import request_handler


@patch('app.components.request_handler.make_request')
def test_get_json_success(mock_make_request):
    mock_response = Mock()
    mock_response.json.return_value = {"key": "value"}
    mock_make_request.return_value = mock_response

    url = "http://example.com"

    result = request_handler.get_json(url)

    assert result == {"key": "value"}
    mock_make_request.assert_called_once_with(url, 'GET', headers=None, data=None, timeout=5)


@patch('app.components.request_handler.make_request')
def test_get_json_no_response(mock_make_request):
    mock_make_request.return_value = None

    url = "http://example.com"

    result = request_handler.get_json(url)

    assert result is None
    mock_make_request.assert_called_once_with(url, 'GET', headers=None, data=None, timeout=5)


@patch('app.components.request_handler.make_request')
@patch('app.components.request_handler.log')
def test_get_json_json_decode_error(mock_log, mock_make_request):
    # Arrange: Simulate a response that raises a JSONDecodeError
    mock_response = Mock()
    mock_response.json.side_effect = json.JSONDecodeError("Expecting value", "", 0)
    mock_make_request.return_value = mock_response

    url = "http://example.com"

    # Act: Call the function
    result = request_handler.get_json(url)

    # Assert: Ensure the function returns None on JSON decode error
    assert result is None
    mock_make_request.assert_called_once_with(url, 'GET', headers=None, data=None, timeout=5)
    mock_log.error.assert_called_once_with(f"JSON decode error for {url}: Expecting value: line 1 column 1 (char 0)")


@patch('requests.put')
def test_make_request_put_success(mock_put):
    response_data = b'{"key": "value"}'
    mock_response = Mock()
    mock_response.content = response_data
    mock_put.return_value = mock_response

    url = "http://example.com/api"
    data = {"data_key": "data_value"}

    result = request_handler.make_request(url, method="PUT", data=data)

    mock_put.assert_called_once_with(url, headers=None, data=data, timeout=5)
    assert result.content == response_data


@patch('requests.get')
def test_make_request_429(mock_get):
    # Simulate a 429 Too Many Requests response
    mock_response = Mock()
    mock_response.status_code = 429
    mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("429 Too Many Requests")
    mock_get.return_value = mock_response

    # Call the function
    result = request_handler.make_request("http://example.com", method="GET")

    # Assertions
    mock_get.assert_called_once_with("http://example.com", headers=None, data=None, timeout=5)
    assert result is None


@patch('requests.get')
def test_make_request_get_failure(mock_get):
    mock_get.side_effect = requests.RequestException("Connection error")

    url = "http://example.com/api"

    result = request_handler.make_request(url)

    mock_get.assert_called_once_with(url, headers=None, data=None, timeout=5)
    assert result is None


@patch('requests.put')
def test_make_request_put_failure(mock_put):
    mock_put.side_effect = requests.RequestException("Connection error")

    url = "http://example.com/api"
    data = {"data_key": "data_value"}

    result = request_handler.make_request(url, method="PUT", data=data)

    mock_put.assert_called_once_with(url, headers=None, data=data, timeout=5)
    assert result is None


def test_make_request_unsupported_method():
    result = request_handler.make_request("http://example.com/api", method="POST")

    assert result is None


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
    mock_get.assert_called_once_with("http://example.com", headers=None, timeout=10)
    assert any(f"Sleeping for " in str(call) for call in mock_log.debug.call_args_list)
    mock_sleep.assert_called()


@patch('app.components.request_handler.make_request')
@patch('time.sleep')
@patch('app.components.request_handler.log')
def test_get_with_retry_http_429(mock_log, mock_sleep, mock_get):
    # Simulate an HTTP 429 response which would be None followed by a successful response
    mock_response_success = Mock()
    mock_response_success.status_code = 200
    mock_response_success.content = b"<html><body>Success</body></html>"
    mock_get.side_effect = [None, mock_response_success]

    result = request_handler.get_with_retry("http://example.com")

    assert result is not None
    assert mock_get.call_count == 2
    assert any(f"Retrying http://example.com in " in str(call) for call in mock_log.info.call_args_list)
    assert any(f"Sleeping for " in str(call) for call in mock_log.debug.call_args_list)
    assert mock_sleep.call_count == 2
