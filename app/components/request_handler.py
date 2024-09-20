from .logger import Logger
import json
import random
import requests
import time

log = Logger('__name__')


def make_request(url, method='GET', headers=None, data=None, timeout=5):
    """
    Helper function to make an HTTP request and handle the response.
    :param url: The URL to send the request to.
    :param method: The HTTP method ('GET' or 'PUT').
    :param headers:
    :param data: The data to be sent in the request body (for 'PUT' method).
    :param timeout: The timeout for the request.
    :return: The parsed JSON response or None if there was an error.
    """
    try:
        # Use a dictionary to map HTTP methods to requests functions
        methods = {
            "GET": requests.get,
            "PUT": requests.put
        }

        if method not in methods:
            log.error(f"Unsupported HTTP method: {method}")
            return None

        response = methods[method](url, headers=headers, data=data, timeout=timeout)
        response.raise_for_status()  # Raise exception for 4xx/5xx errors
        return response
    except requests.exceptions.RequestException as e:
        status_code = getattr(e.response, 'status_code', 'Unknown')
        log.error(f"{method} {url} failed with status code: {status_code}")
        if status_code == 'Unknown':
            log.error(f"Unknown: {e}")
        return None


def get_json(url, method='GET', headers=None, data=None, timeout=5):
    response = make_request(url, method, headers=headers, data=data, timeout=timeout)
    if response:
        try:
            return response.json()  # Try to parse the response as JSON
        except json.JSONDecodeError as e:
            log.error(f"JSON decode error for {url}: {e}")
    return None


def get_with_retry(url, headers=None, max_retries=5, delay=4):
    # Get the URL with retries and delay
    for attempt in range(max_retries):
        response = make_request(url, headers=headers, timeout=10)
        if response:
            sleep_time = random.uniform(1, 3)  # Sleep for a random time between 1 and 3 seconds
            log.debug(f"Sleeping for {sleep_time:.2f}s")
            time.sleep(sleep_time)
            return response
        delay = min(delay * 2 + random.uniform(0, 2), 60)
        log.info(f"Retrying in {delay:.2f}s...")
        time.sleep(delay)
    log.error(f"Failed to retrieve {url} after {max_retries} attempts.")
    return None
