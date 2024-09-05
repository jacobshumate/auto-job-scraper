import os
import sys

import requests

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../app')))

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
STATUS_RUNNING = 'running'
TIMEOUT = 60
CHECK_INTERVAL = 5
INITIAL_DELAY = 15


def test_reset_vpn_success():
    with patch('app.components.vpn_manager.get_vpn_ip') as mock_get_vpn_ip, \
            patch('app.components.vpn_manager.restart_gluetun_service') as mock_restart_gluetun, \
            patch('app.components.vpn_manager.wait_for_gluetun_to_be_ready') as mock_wait_for_ready, \
            patch('time.sleep') as mock_sleep, \
            patch('app.components.vpn_manager.log') as mock_log:
        # Arrange: Simulate the VPN IP change
        mock_get_vpn_ip.side_effect = ['123.45.67.89', '98.76.54.32']
        mock_wait_for_ready.return_value = True

        # Act
        result = vpn_manager.reset_vpn()

        # Assert
        assert result is True
        mock_get_vpn_ip.assert_called()
        mock_restart_gluetun.assert_called_once()
        mock_sleep.assert_called_once_with(INITIAL_DELAY)
        mock_log.info.assert_any_call("Resetting VPN connection...")
        mock_log.info.assert_any_call(f"Current VPN IP reset to: 98.76.54.32, "
                                      f"processed in 0.00 seconds")


def test_reset_vpn_fail_to_get_current_ip():
    with patch('app.components.vpn_manager.get_vpn_ip') as mock_get_vpn_ip, \
            patch('app.components.vpn_manager.log') as mock_log:
        # Arrange: Simulate failure to get current VPN IP
        mock_get_vpn_ip.return_value = None

        # Act
        result = vpn_manager.reset_vpn()

        # Assert
        assert result is False
        mock_get_vpn_ip.assert_called_once()
        mock_log.error.assert_called_once_with("Failed to obtain current vpn ip.")


def test_reset_vpn_fail_to_change_ip():
    with patch('app.components.vpn_manager.get_vpn_ip') as mock_get_vpn_ip, \
            patch('app.components.vpn_manager.restart_gluetun_service') as mock_restart_gluetun, \
            patch('app.components.vpn_manager.wait_for_gluetun_to_be_ready') as mock_wait_for_ready, \
            patch('time.sleep') as mock_sleep, \
            patch('app.components.vpn_manager.log') as mock_log:
        # Arrange: Simulate no change in VPN IP
        mock_get_vpn_ip.side_effect = ['123.45.67.89', '123.45.67.89']  # Same IP returned
        mock_wait_for_ready.return_value = True

        # Act
        result = vpn_manager.reset_vpn()

        # Assert
        assert result is False
        mock_get_vpn_ip.assert_called()
        mock_restart_gluetun.assert_called_once()
        mock_sleep.assert_called_once_with(INITIAL_DELAY)
        mock_log.error.assert_called_with("Failed to change to new VPN ip: 123.45.67.89, "
                                          "processed in 0.00 seconds")


def test_reset_vpn_fail_gluetun_status():
    with patch('app.components.vpn_manager.get_vpn_ip') as mock_get_vpn_ip, \
            patch('app.components.vpn_manager.restart_gluetun_service') as mock_restart_gluetun, \
            patch('app.components.vpn_manager.wait_for_gluetun_to_be_ready') as mock_wait_for_ready, \
            patch('time.sleep') as mock_sleep:
        # Arrange: Simulate failure in Gluetun service status
        mock_get_vpn_ip.return_value = '123.45.67.89'
        mock_wait_for_ready.return_value = False  # Simulate Gluetun service failure

        # Act
        result = vpn_manager.reset_vpn()

        # Assert
        assert result is False
        mock_get_vpn_ip.assert_called()
        mock_restart_gluetun.assert_called_once()
        mock_sleep.assert_called_once_with(INITIAL_DELAY)
        # mock_log.error.assert_called_with("Timeout reached. Gluetun service did not start.")


def test_wait_for_gluetun_to_be_ready_success():
    with patch('app.components.vpn_manager.is_gluetun_service_running') as mock_is_running, \
            patch('time.sleep') as mock_sleep:
        # Arrange: Simulate the service returning True after 2 retries
        mock_is_running.side_effect = [False, False, True]

        # Act
        result = vpn_manager.wait_for_gluetun_to_be_ready(timeout=30, check_interval=5)

        # Assert
        assert result is True
        assert mock_is_running.call_count == 3  # Called three times before success
        mock_sleep.assert_any_call(5)  # Initial sleep interval
        mock_sleep.assert_any_call(10)  # Exponential backoff interval


def test_wait_for_gluetun_to_be_ready_timeout():
    with patch('app.components.vpn_manager.is_gluetun_service_running') as mock_is_running, \
             patch('time.sleep') as mock_sleep, \
             patch('app.components.vpn_manager.log') as mock_log:
        # Arrange: Simulate the service never becoming ready
        mock_is_running.return_value = False

        # Act
        result = vpn_manager.wait_for_gluetun_to_be_ready(timeout=1, check_interval=5)

        # Assert
        assert result is False
        mock_is_running.assert_called()  # Should call multiple times
        mock_sleep.assert_called()  # Check that it did retry with sleep intervals
        mock_log.error.assert_called_with("Timeout reached. Gluetun service did not start.")


def test_is_gluetun_service_running_success():
    with patch('app.components.vpn_manager.make_request') as mock_make_request:
        # Arrange: Simulate a successful response where the service is running
        mock_make_request.return_value = {'status': STATUS_RUNNING}

        # Act
        result = vpn_manager.is_gluetun_service_running()

        # Assert
        mock_make_request.assert_called_once_with(GLUETUN_STATUS_URL)
        assert result is True


def test_is_gluetun_service_running_failure():
    with patch('app.components.vpn_manager.make_request') as mock_make_request:
        # Arrange: Simulate a response where the service is not running
        mock_make_request.return_value = {'status': 'stopped'}

        # Act
        result = vpn_manager.is_gluetun_service_running()

        # Assert
        mock_make_request.assert_called_once_with(GLUETUN_STATUS_URL)
        assert result is False


def test_restart_gluetun_service():
    with patch('app.components.vpn_manager.make_request') as mock_make_request, \
            patch('app.components.vpn_manager.log.info') as mock_log_info:
        # Arrange: Simulate a successful PUT request
        mock_make_request.return_value = {"outcome": "success"}

        # Act
        vpn_manager.restart_gluetun_service()

        # Assert
        mock_make_request.assert_called_once_with(GLUETUN_STATUS_URL, method='PUT', data='{"status":"stopped"}')
        mock_log_info.assert_called_once_with('Gluetun status: success')


def test_get_vpn_ip_success():
    with patch('app.components.vpn_manager.make_request') as mock_make_request:
        # Arrange
        mock_make_request.return_value = {IP: '123.45.67.89'}

        # Act
        result = vpn_manager.get_vpn_ip()

        # Assert
        mock_make_request.assert_called_once_with(IP_INFO_URLS[0], timeout=10)
        assert result == '123.45.67.89'


def test_get_vpn_ip_fail():
    with patch('app.components.vpn_manager.make_request') as mock_make_request, \
            patch('time.sleep') as mock_sleep:
        # Arrange: make_request returns None (simulating failed requests)
        mock_make_request.return_value = None

        # Act
        result = vpn_manager.get_vpn_ip()

        # Assert
        assert result is None
        assert mock_make_request.call_count == len(IP_INFO_URLS)
        mock_sleep.assert_called()  # Ensure it tried to sleep after failure


def test_get_vpn_ip_exponential_backoff():
    with patch('app.components.vpn_manager.make_request') as mock_make_request, \
            patch('time.sleep') as mock_sleep:
        # Arrange: simulate multiple failures, then a successful response
        mock_make_request.side_effect = [None, None, {IP: '123.45.67.89'}]

        # Act
        result = vpn_manager.get_vpn_ip()

        # Assert
        assert result == '123.45.67.89'
        assert mock_make_request.call_count == 3
        assert mock_sleep.call_count == 2
        mock_sleep.assert_any_call(5)
        mock_sleep.assert_any_call(10)


def test_make_request_get_success():
    with patch('requests.get') as mock_get:
        response_data = {"key": "value"}
        # Arrange
        mock_response = Mock()
        mock_response.json.return_value = response_data
        mock_get.return_value = mock_response

        url = "http://example.com/api"

        # Act
        result = vpn_manager.make_request(url)

        # Assert
        mock_get.assert_called_once_with(url, timeout=5)
        assert result == response_data


def test_make_request_put_success():
    with patch('requests.put') as mock_put:
        response_data = {"key": "value"}
        # Arrange
        mock_response = Mock()
        mock_response.json.return_value = response_data
        mock_put.return_value = mock_response

        url = "http://example.com/api"
        data = {"data_key": "data_value"}

        # Act
        result = vpn_manager.make_request(url, method="PUT", data=data)

        # Assert
        mock_put.assert_called_once_with(url, data=data, timeout=5)
        assert result == response_data


def test_make_request_get_failure():
    with patch('requests.get') as mock_get:
        # Arrange
        mock_get.side_effect = requests.RequestException("Connection error")

        url = "http://example.com/api"

        # Act
        result = vpn_manager.make_request(url)

        # Assert
        mock_get.assert_called_once_with(url, timeout=5)
        assert result is None


def test_make_request_put_failure():
    with patch('requests.put') as mock_put:
        # Arrange
        mock_put.side_effect = requests.RequestException("Connection error")

        url = "http://example.com/api"
        data = {"data_key": "data_value"}

        # Act
        result = vpn_manager.make_request(url, method="PUT", data=data)

        # Assert
        mock_put.assert_called_once_with(url, data=data, timeout=5)
        assert result is None


def test_make_request_unsupported_method():
    # Act
    result = vpn_manager.make_request("http://example.com/api", method="POST")

    # Assert
    assert result is None


def test_check_status():
    json_response = {"status": "running"}
    assert vpn_manager.check_status(json_response, "running")

    json_response = {"status": "stopped"}
    assert not vpn_manager.check_status(json_response, "running")
