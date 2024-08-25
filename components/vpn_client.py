from components.logger import Logger
import requests
import time as tm

LOCAL_IP="http://127.0.0.1:8000"
STATUS_URL="/v1/openvpn/status"
STATUS="status"
STATUS_RUNNING="running"
STATUS_STOPPED="stopped"
IP_INFO_URL= "https://ipinfo.io"
IP="ip"

log = Logger('__main__')

def restart_vpn_client(retries=3, delay=30):
    try:
        status = request(LOCAL_IP + STATUS_URL, "get")[STATUS]
        if STATUS_RUNNING == status:
            current_ip = request(IP_INFO_URL, "get")[IP]
            while retries > 0:
                request(LOCAL_IP + STATUS_URL, "put", '{"status":"stopped"}')
                log.info(f"Delaying for {delay}s")
                tm.sleep(delay)
                status = request(LOCAL_IP + STATUS_URL, "get")[STATUS]
                next_ip = request(IP_INFO_URL, "get")[IP]
                if STATUS_RUNNING == status and next_ip != current_ip:
                    log.info(f"VPN CLient succesfully restarted with new ip: {next_ip}")
                    return True
                retries -= 1
        else:
            log.error(f"VPN Client has stopped running!")
            return False
    except Exception as e:
        log.error(f"An error occurred: {e}")
        return True
    return False

def request(url, method, body=None, retries=3, delay=1):
    # Get the URL with retries and delay
    for i in range(retries):
        try:
            r = get_or_put(method, url, body)
            if r.status_code != 200:
                log.error(f"FAILED to {method} URL: {url}, response status code: {r.status_code} message: {r.content}")
                tm.sleep(delay)
                continue
            log.info(f"Response content: {r.content} headers: {r.headers}")
            return r.json()
        except requests.exceptions.Timeout:
            log.info(f"Timeout occurred for URL: {url}, retrying in {delay}s...")
            tm.sleep(delay)
            continue
        except Exception as e:
            log.error(f"An error occurred while retrieving the URL: {url}, error: {e}")
    return None

def get_or_put(method, url, body):
    match method:
        case "get":
            return requests.get(url, headers={}, timeout=5)
        case "put":
            return requests.put(url, data=body, headers={}, timeout=5)
        case _:
            return None