import requests
from unittest.mock import patch, Mock
from app.components import vpn_manager

# Sample constants for testing
IP = 'ip'
IP_INFO_URLS = [
    "https://ipinfo.io",
    "https://api.ipify.org?format=json",
    "https://ifconfig.co/json"
]
GLUETUN_STATUS_URL = "http://127.0.0.1:8000/v1/openvpn/status"
TIMEOUT = 60
CHECK_INTERVAL = 5
INITIAL_DELAY = 15


@patch('app.components.vpn_manager.get_vpn_ip', side_effect=['123.45.67.89', '98.76.54.32']) # Arrange: Simulate the VPN IP change
@patch('app.components.vpn_manager.restart_gluetun_service')
@patch('app.components.vpn_manager.wait_for_gluetun_to_be_ready', return_value=True)
@patch('time.sleep')
@patch('app.components.vpn_manager.log')
def test_reset_vpn_success(mock_log, mock_sleep, mock_wait_for_ready, mock_restart_gluetun, mock_get_vpn_ip):
    result = vpn_manager.reset_vpn()

    assert result is True
    mock_get_vpn_ip.assert_called()
    mock_restart_gluetun.assert_called_once()
    mock_sleep.assert_called_once_with(INITIAL_DELAY)
    mock_log.info.assert_any_call("Resetting VPN connection...")
    mock_log.info.assert_any_call(f"Current VPN IP reset to: 98.76.54.32, "
                                  f"processed in 0.00 seconds")


@patch('app.components.vpn_manager.get_vpn_ip', return_value=None) # Simulate failure to get current VPN IP
@patch('app.components.vpn_manager.log')
def test_reset_vpn_fail_to_get_current_ip(mock_log, mock_get_vpn_ip):
    result = vpn_manager.reset_vpn()

    assert result is False
    mock_get_vpn_ip.assert_called_once()
    mock_log.error.assert_called_once_with("Failed to obtain current vpn ip.")


@patch('app.components.vpn_manager.get_vpn_ip', side_effect=['123.45.67.89', '123.45.67.89']) # Simulate no change in VPN IP
@patch('app.components.vpn_manager.restart_gluetun_service')
@patch('app.components.vpn_manager.wait_for_gluetun_to_be_ready', return_value=True)
@patch('time.sleep')
@patch('app.components.vpn_manager.log')
def test_reset_vpn_fail_to_change_ip(mock_log, mock_sleep, mock_wait_for_ready, mock_restart_gluetun, mock_get_vpn_ip):
    result = vpn_manager.reset_vpn()

    assert result is False
    mock_get_vpn_ip.assert_called()
    mock_restart_gluetun.assert_called_once()
    mock_sleep.assert_called_once_with(INITIAL_DELAY)
    mock_log.error.assert_called_with("Failed to change to new VPN ip: 123.45.67.89, "
                                      "processed in 0.00 seconds")


@patch('app.components.vpn_manager.get_vpn_ip', return_value='123.45.67.89') # Simulate failure in Gluetun service status
@patch('app.components.vpn_manager.restart_gluetun_service')
@patch('app.components.vpn_manager.wait_for_gluetun_to_be_ready', return_value=False) # Simulate Gluetun service failure
@patch('time.sleep')
def test_reset_vpn_fail_gluetun_status(mock_sleep, mock_wait_for_ready, mock_restart_gluetun, mock_get_vpn_ip):
    result = vpn_manager.reset_vpn()

    assert result is False
    mock_get_vpn_ip.assert_called()
    mock_restart_gluetun.assert_called_once()
    mock_sleep.assert_called_once_with(INITIAL_DELAY)


@patch('app.components.vpn_manager.is_gluetun_service_running', side_effect=[False, False, True]) # Simulate the service returning True after 2 retries
@patch('time.sleep')
def test_wait_for_gluetun_to_be_ready_success(mock_sleep, mock_is_running):
    result = vpn_manager.wait_for_gluetun_to_be_ready(timeout=30, check_interval=5)

    assert result is True
    assert mock_is_running.call_count == 3  # Called three times before success
    mock_sleep.assert_any_call(5)  # Initial sleep interval
    mock_sleep.assert_any_call(10)  # Exponential backoff interval


@patch('app.components.vpn_manager.is_gluetun_service_running', return_value=False) # Simulate the service never becoming ready
@patch('time.sleep')
@patch('app.components.vpn_manager.log')
def test_wait_for_gluetun_to_be_ready_timeout(mock_log, mock_sleep, mock_is_running):
    result = vpn_manager.wait_for_gluetun_to_be_ready(timeout=1, check_interval=5)

    assert result is False
    mock_is_running.assert_called()  # Should call multiple times
    mock_sleep.assert_called()  # Check that it did retry with sleep intervals
    mock_log.error.assert_called_with("Timeout reached. Gluetun service did not start.")


@patch('app.components.vpn_manager.make_request', return_value={'status': 'running'}) # Simulate a successful response where the service is running
def test_is_gluetun_service_running_success(mock_make_request):
    result = vpn_manager.is_gluetun_service_running()

    mock_make_request.assert_called_once_with(GLUETUN_STATUS_URL)
    assert result is True


@patch('app.components.vpn_manager.make_request', return_value={'status': 'stopped'}) # Simulate a response where the service is not running
def test_is_gluetun_service_running_failure(mock_make_request):
    result = vpn_manager.is_gluetun_service_running()

    mock_make_request.assert_called_once_with(GLUETUN_STATUS_URL)
    assert result is False


@patch('app.components.vpn_manager.make_request', return_value={'outcome': 'success'}) # Simulate a successful PUT request
@patch('app.components.vpn_manager.log.info')
def test_restart_gluetun_service(mock_log_info, mock_make_request):
    vpn_manager.restart_gluetun_service()

    mock_make_request.assert_called_once_with(GLUETUN_STATUS_URL, method='PUT', data='{"status":"stopped"}')
    mock_log_info.assert_called_once_with('Gluetun status: success')


@patch('app.components.vpn_manager.make_request', return_value={IP: '123.45.67.89'})
def test_get_vpn_ip_success(mock_make_request):
    result = vpn_manager.get_vpn_ip()

    mock_make_request.assert_called_once_with(IP_INFO_URLS[0], timeout=10)
    assert result == '123.45.67.89'


@patch('app.components.vpn_manager.make_request', return_value=None) # Simulate a failed request
@patch('time.sleep')
def test_get_vpn_ip_fail(mock_sleep, mock_make_request):
    result = vpn_manager.get_vpn_ip()

    assert result is None
    assert mock_make_request.call_count == len(IP_INFO_URLS)
    mock_sleep.assert_called()  # Ensure it tried to sleep after failure


@patch('app.components.vpn_manager.make_request', side_effect=[None, None, {IP: '123.45.67.89'}]) # Simulate multiple failures, then a successful response
@patch('time.sleep')
def test_get_vpn_ip_exponential_backoff(mock_sleep, mock_make_request):
    result = vpn_manager.get_vpn_ip()

    assert result == '123.45.67.89'
    assert mock_make_request.call_count == 3
    assert mock_sleep.call_count == 2
    mock_sleep.assert_any_call(5)
    mock_sleep.assert_any_call(10)


@patch('requests.get')
def test_make_request_get_success(mock_get):
    response_data = {"key": "value"}
    mock_response = Mock()
    mock_response.json.return_value = response_data
    mock_get.return_value = mock_response

    url = "http://example.com/api"

    result = vpn_manager.make_request(url)

    mock_get.assert_called_once_with(url, timeout=5)
    assert result == response_data


@patch('requests.put')
def test_make_request_put_success(mock_put):
    response_data = {"key": "value"}
    mock_response = Mock()
    mock_response.json.return_value = response_data
    mock_put.return_value = mock_response

    url = "http://example.com/api"
    data = {"data_key": "data_value"}

    result = vpn_manager.make_request(url, method="PUT", data=data)

    mock_put.assert_called_once_with(url, data=data, timeout=5)
    assert result == response_data


@patch('requests.get')
def test_make_request_get_failure(mock_get):
    mock_get.side_effect = requests.RequestException("Connection error")

    url = "http://example.com/api"

    result = vpn_manager.make_request(url)

    mock_get.assert_called_once_with(url, timeout=5)
    assert result is None


@patch('requests.put')
def test_make_request_put_failure(mock_put):
    mock_put.side_effect = requests.RequestException("Connection error")

    url = "http://example.com/api"
    data = {"data_key": "data_value"}

    result = vpn_manager.make_request(url, method="PUT", data=data)

    mock_put.assert_called_once_with(url, data=data, timeout=5)
    assert result is None


def test_make_request_unsupported_method():
    result = vpn_manager.make_request("http://example.com/api", method="POST")

    assert result is None


def test_check_status():
    json_response = {"status": "running"}
    assert vpn_manager.check_status(json_response, "running")

    json_response = {"status": "stopped"}
    assert not vpn_manager.check_status(json_response, "running")
