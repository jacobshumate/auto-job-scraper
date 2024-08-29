from bs4 import BeautifulSoup
from .logger import Logger
import random
import requests
import time

log = Logger('__main__')

def get_with_retry(url, config, headers=None, max_retries=5, delay=4):
    # Get the URL with retries and delay
    for attempt in range(max_retries):
        try:
            if len(config['proxies']) > 0:
                response = requests.get(url, headers=headers, proxies=config['proxies'], timeout=10)
            else:
                response = requests.get(url, headers=headers, timeout=10)
            delay = min(delay * 2 + random.uniform(0, 2), 60)
            if response.status_code == 429:
                log.info(f"Too many requests for {url}, retrying in {delay:.2f}s...")
                time.sleep(delay)
                continue
            else:
                response.raise_for_status()
                sleep_time = random.uniform(1, 3) # Sleep for a random time between 1 and 3 seconds
                log.info(f"Sleeping for {sleep_time:.2f}s")
                time.sleep(sleep_time)
                return BeautifulSoup(response.content, 'html.parser')
        except requests.exceptions.RequestException as e:
            log.info(f"Request failed for {url} due to {e}, retrying in {delay:.2f}s...")
            time.sleep(delay)
            continue
        except Exception as e:
            log.error(f"An error occurred while retrieving {url}, error: {e}")
            break
    return None

