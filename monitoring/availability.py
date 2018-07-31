import logging
import csv
from datetime import datetime
import pytz
from functools import partial
import threading
import requests
from monitoring.scheduler import ThreadedScheduler, run_threaded_job
from monitoring.common import HTTPCheckResult


logger = logging.getLogger("availability_monitor")
info, debug, error = logger.info, logger.debug, logger.error

csv_write_lock = threading.Lock()


DEFAULT_CHECK_INTERVAL = 0.5


def get_service_urls(csv_path, col_no):
    with open(csv_path) as csv_file:
        reader = csv.reader(csv_file, delimiter="\t")
        return [r[col_no] for r in reader]


def check_availability_job(url, output_path, timeout=None):
    """
    Checks the availability of a URL, and appends the result to a CSV file.
    URL's are verified using a streaming GET request - the connection is severed
    once the headers are received, to avoid impacting services with a sizeable
    response content size.

    Parameters:
          url(str) : The URL to check
          output_path(str): The path of the CSV file to append the results to.
          timeout(float): The timeout in seconds for the GET requests - if `None`,
            defaults to `DEFAULT_CHECK_INTERVAL`.
    """
    timeout = timeout or DEFAULT_CHECK_INTERVAL

    info(f"Checking {url}")
    try:
        with requests.get(url, timeout=timeout, stream=True) as r:
            try:
                content_length = int(r.headers["Content-Length"])
            except (KeyError, ValueError):
                content_length = None

            result = HTTPCheckResult(
                status_code=r.status_code,
                content_length=content_length,
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
                    url,
                    result.status_code,
                    result.content_length,
                    result.content_type,
                    result.duration,
                    result.last_modified,
                    1 if result.timeout else 0,
                    1 if result.connection_error else 0,
                ]
            )


class AvailabilityMonitor:
    """
    Monitors availability of a set of URL's.
    A check job is scheduled for each URL, then the scheduler main loop and
    each job execution are run in separate threads.

    Parameters:
        service_urls(list): URL's to monitor
        output_path(str): The path of the CSV file to append the results to.
        check_interval(float): Interval in seconds when each URL is to be checked.
        timeout(float): The timeout in seconds for the GET requests - if `None`,
            defaults to `DEFAULT_CHECK_INTERVAL`.
    """

    def __init__(self, service_urls, output_path, check_interval, timeout=None):
        self.urls = service_urls
        self.output_path = output_path
        self.check_interval = check_interval
        self.timeout = timeout or DEFAULT_CHECK_INTERVAL
        self.scheduler = ThreadedScheduler()

    def schedule_jobs(self):
        """
        Schedules a job for each service URL.
        """
        for url in self.urls:
            info(f"Scheduling check for {url} every {self.check_interval} seconds")
            self.scheduler.every(self.check_interval).seconds.do(
                run_threaded_job,
                partial(
                    check_availability_job,
                    url=url,
                    output_path=self.output_path,
                    timeout=self.timeout,
                ),
            )

    def run(self, interval=1):
        """
        Schedules the jobs and runs the scheduler continuously, on default delay of 1 second.

        Returns:
            The scheduler loop's thread poison pill (a `threading.Event` instance).
        """
        self.schedule_jobs()
        info("Starting scheduler")
        return self.scheduler.run_continuously(interval)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Run the INSPIRE endpoints availability monitor"
    )
    parser.add_argument("--endpoints-csv", help="Path to CSV with endpoint URL's")
    parser.add_argument("--output", help="Path to monitoring output file")
    parser.add_argument(
        "--urls-col-no", default=0, type=int, help="URL's column number in the CSV file"
    )
    parser.add_argument(
        "--check-interval",
        default=300,
        type=int,
        help="Interval to check every endpoint at, in seconds",
    )

    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.getLogger("schedule").setLevel(logging.WARNING)

    urls = get_service_urls(args.endpoints_csv, col_no=args.urls_col_no)
    monitor = AvailabilityMonitor(
        service_urls=urls, output_path=args.output, check_interval=args.check_interval
    )
    monitor.run()
