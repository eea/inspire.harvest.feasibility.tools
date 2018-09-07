import logging
import csv
from datetime import datetime
import pytz
import requests
from monitoring.common import HTTPCheckResult, Monitor, get_service_urls


logger = logging.getLogger("reliability_check")
info, debug, error = logger.info, logger.debug, logger.error


def check_reliability(url, url_id, output_path, csv_write_lock, timeout):
    """
    Checks the reliability of a URL, and appends the result to a CSV file.

    Parameters:
          url(str) : The URL to check
          url_id(int) : The is written to file instead of the URL, for correlation.
          output_path(str): The path of the CSV file to append the results to.
          csv_write_lock (threading.Lock): Lock for writing to CSV.
          timeout(float): The timeout in seconds for the GET requests - if `None`,
            defaults to `DEFAULT_CHECK_INTERVAL`.
    """

    info(f"Checking {url}")
    try:
        with requests.get(url, timeout=timeout, stream=True) as r:
            result = HTTPCheckResult(
                status_code=r.status_code,
                content_length=len(r.content),
                content_type=r.headers.get("Content-Type"),
                duration=r.elapsed.total_seconds(),
                last_modified=r.headers.get("Last-Modified"),
            )
    except requests.exceptions.Timeout:
        result = HTTPCheckResult(timeout=True)
    except requests.exceptions.ConnectionError:
        result = HTTPCheckResult(connection_error=True)

    with csv_write_lock:
        with open(output_path, "a") as f:
            w = csv.writer(f, delimiter="\t")
            w.writerow(
                [
                    datetime.now(pytz.UTC).isoformat(),
                    url_id,
                    result.status_code,
                    result.content_length,
                    result.content_type,
                    result.duration,
                    result.last_modified,
                    1 if result.timeout else 0,
                    1 if result.connection_error else 0,
                ]
            )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Run the INSPIRE endpoints reliability monitor"
    )
    parser.add_argument("--endpoints-csv", help="Path to CSV with endpoint URL's")
    parser.add_argument("--output", help="Path to monitoring output file")
    parser.add_argument(
        "--urls-col-no", default=0, type=int, help="URL's column number in the CSV file"
    )
    parser.add_argument(
        "--check-interval",
        default=43200,
        type=int,
        help="Interval to check every endpoint at, in seconds. Defaults to 12h.",
    )

    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.getLogger("schedule").setLevel(logging.WARNING)

    urls = get_service_urls(args.endpoints_csv, col_no=args.urls_col_no)
    monitor = Monitor(
        service_urls=urls,
        check_func=check_reliability,
        output_path=args.output,
        check_interval=args.check_interval,
    )

    monitor.run()
