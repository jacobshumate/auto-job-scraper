from .logger import Logger
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
    :param proxies:
    :param data: The data to be sent in the request body (for 'PUT' method).
    :param timeout: The timeout for the request.
    :return: The parsed JSON response or None if there was an error.
    """
    try:
        match method:
            case "GET":
                response = requests.get(url, headers=headers, timeout=timeout)
            case "PUT":
                response = requests.put(url, headers=headers, data=data, timeout=timeout)
            case _:
                log.error(f"Unsupported HTTP method: {method}")
                return None
        response.raise_for_status()  # Raise an exception for 4xx/5xx errors
        return response
    except requests.RequestException as e:
        log.error(f"{method} {url} failed: {e}")
        return None


def get_with_retry(url, headers=None, max_retries=5, delay=4):
    # Get the URL with retries and delay
    for attempt in range(max_retries):
        try:
            response = make_request(url, headers, timeout=10)
            delay = min(delay * 2 + random.uniform(0, 2), 60)
            if response.status_code == 429:
                log.info(f"Too many requests for {url}, retrying in {delay:.2f}s...")
                time.sleep(delay)
                continue
            else:
                response.raise_for_status()
                sleep_time = random.uniform(1, 3)  # Sleep for a random time between 1 and 3 seconds
                log.debug(f"Sleeping for {sleep_time:.2f}s")
                time.sleep(sleep_time)
                return response
        except requests.exceptions.RequestException as e:
            log.info(f"Request failed for {url} due to {e}, retrying in {delay:.2f}s...")
            time.sleep(delay)
            continue
        except Exception as e:
            log.error(f"An error occurred while retrieving {url}, error: {e}")
            break
    return None
