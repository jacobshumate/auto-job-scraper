from .logger import Logger
import requests
import time

# Setup log
log = Logger('__name__')


# Configuration
GLUETUN_STATUS_URL = "http://127.0.0.1:8000/v1/openvpn/status"
STATUS = "status"
STATUS_RUNNING = "running"
STATUS_STOPPED = "stopped"
IP_INFO_URLS = [ # List of urls for getting ips
    "https://ipinfo.io",
    "https://api.ipify.org?format=json",
    "https://ifconfig.co/json"
]
IP = "ip"
TIMEOUT = 300  # Total time to wait (in seconds)
CHECK_INTERVAL = 5  # Initial interval between checks (in seconds)
INITIAL_DELAY = 15


def reset_vpn():
    """Retrieve current VPN ip, reset VPN, delay, wait for status to be
    running then check new vpn ip against current and proceed forward."""
    start_time = time.perf_counter()
    log.info("Resetting VPN connection...")
    # 1. Get current VPN ip
    current_vpn_ip = get_vpn_ip()
    if not current_vpn_ip:
        log.error(f"Failed to obtain current vpn ip.")
        return False
    log.info(f"Current VPN IP: {current_vpn_ip}")

    # 2. Reset VPN connection
    restart_gluetun_service()

    # 3. Delay before checking status
    log.info(f"Delaying for {INITIAL_DELAY}s before checking status.")
    time.sleep(INITIAL_DELAY)

    # 34 Wait for Gluetun to be ready with new VPN ip assigned
    if wait_for_gluetun_to_be_ready():
        new_vpn_ip = get_vpn_ip()
        end_time = time.perf_counter()
        if new_vpn_ip and new_vpn_ip != current_vpn_ip:
            log.info(f"Current VPN IP reset to: {new_vpn_ip}, "
                     f"processed in {end_time - start_time:.2f} seconds")
            return True
        else:
            log.error(f"Failed to change to new VPN ip: {new_vpn_ip}, "
                          f"processed in {end_time - start_time:.2f} seconds")
    return False


def wait_for_gluetun_to_be_ready(timeout=TIMEOUT, check_interval=CHECK_INTERVAL):
    """Wait for Gluetun service to reach status: running.
    :param timeout: The timeout for the request.
    :param check_interval: Initial interval between checks (in seconds)
    :return: True if gluetun service is running
    """
    start_time = time.time()
    while time.time() - start_time < timeout:
        if is_gluetun_service_running():
            return True
        log.info(f"Service not ready. Retrying in {check_interval} seconds...")
        time.sleep(check_interval)
        check_interval = min(check_interval * 2, 60)  # Exponential backoff, max 60 seconds

    log.error("Timeout reached. Gluetun service did not start.")
    return False


def is_gluetun_service_running():
    """Check if Gluetun service is running."""
    response_json = make_request(GLUETUN_STATUS_URL)
    return check_status(response_json, STATUS_RUNNING)


def restart_gluetun_service():
    """Restart the Gluetun service."""
    data = '{"status":"stopped"}'
    response_json = make_request(GLUETUN_STATUS_URL, method='PUT', data=data)
    log.info(f"Gluetun status: {response_json.get("outcome")}")


def get_vpn_ip(check_interval=CHECK_INTERVAL):
    """Get current VPN ip"""
    for url in IP_INFO_URLS:
        response_json = make_request(url, timeout=10)
        if not response_json:
            log.info(f"VPN IP not ready. Retrying in {check_interval} seconds...")
            time.sleep(check_interval)
            check_interval = min(check_interval * 2, 60) # Exponential backoff, max 60 seconds
            continue
        ip = response_json.get(IP)
        if ip:
            return ip
    return None


def make_request(url, method='GET', data=None, timeout=5):
    """
    Helper function to make an HTTP request and handle the response.

    :param url: The URL to send the request to.
    :param method: The HTTP method ('GET' or 'PUT').
    :param data: The data to be sent in the request body (for 'PUT' method).
    :param timeout: The timeout for the request.
    :return: The parsed JSON response or None if there was an error.
    """
    try:
        match method:
            case "GET":
                response = requests.get(url, timeout=timeout)
            case "PUT":
                response = requests.put(url, data=data, timeout=timeout)
            case _:
                log.error(f"Unsupported HTTP method: {method}")
                return None
        response.raise_for_status()  # Raise an exception for 4xx/5xx errors
        return response.json()
    except requests.RequestException as e:
        log.error(f"{method} {url} failed: {e}")
        return None


def check_status(response_json, expected_status):
    """
    Helper function to check the status in the JSON response.

    :param response_json: The JSON response from the HTTP request.
    :param expected_status: The expected status string to check against.
    :return: True if the status matches the expected status, False otherwise.
    """
    if response_json:
        status = response_json.get(STATUS)
        log.info(f"Gluetun status: {status}")
        return status == expected_status
    return False
