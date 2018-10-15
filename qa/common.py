import csv
import re
from functools import wraps

import pycountry
import requests
import logme
from lxml import etree


log = logme.log(scope='module', name='inspire_qa')


TIMEOUT_LIMIT = 10


def check(msg, logger):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            _msg = f"CHECK {msg}:"
            result = f(*args, **kwargs)
            if not result:
                logger.error(f"{_msg} FAILED")
            else:
                logger.info(f"{_msg} PASSED")
            return result
        return wrapper
    return decorator


def check_list_errors(msg, logger):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            _msg = f"CHECK {msg}:"
            result, errors = f(*args, **kwargs)
            if not result:
                for err in errors:
                    log.error(err)
                logger.error(f"{_msg} FAILED")
            else:
                logger.info(f"{_msg} PASSED")
            return result
        return wrapper
    return decorator


def load_urls(csv_path):
    with open(csv_path) as csv_file:
        reader = csv.reader(csv_file, delimiter="\t")
        return [(pycountry.countries.get(alpha_2=r[0]), r[1]) for r in reader if not r[0].startswith("#")]


def get_filename(content_disposition):
    """
    Get filename from content-disposition
    """
    if not content_disposition:
        return None
    fname = re.findall("filename=(.+)", content_disposition)
    try:
        return fname[0]
    except IndexError:
        return None


def fetch_url(url, save=True, save_as=None, timeout=TIMEOUT_LIMIT):
    errors = []
    try:
        response = requests.get(url=url, timeout=timeout, allow_redirects=True)
        if not save:
            result = response.content
        elif save_as is None:
            header_file_name = get_filename(response.headers.get("content-disposition"))
            last_segment = url.split("/")[-1]
            if header_file_name is not None:
                save_as = header_file_name
            elif (
                    "&" not in last_segment
                    and "?" not in last_segment
            ):
                save_as = last_segment
            else:
                save_as = "download"

        result = save_as

        with open(save_as, "wb") as f:
            f.write(response.content)

    except requests.exceptions.Timeout:
        errors.append(f"Timeout fetching {url}")
    except (requests.exceptions.ConnectionError, requests.exceptions.ChunkedEncodingError):
        errors.append(f"Connection error fetching {url}")

    return result, errors


def get_tree_from_file(file_path):
    with open(file_path, "rb") as f:
        return etree.parse(f)
