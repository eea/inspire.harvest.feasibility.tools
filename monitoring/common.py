import csv
import logging
from functools import partial
import threading
import attr
from monitoring.scheduler import ThreadedScheduler, run_threaded_job

logger = logging.getLogger("monitor")
info, debug, error = logger.info, logger.debug, logger.error

DEFAULT_CHECK_INTERVAL = 60


@attr.s
class HTTPCheckResult:
    """
    Stores the results of a HTTP check.
    """

    status_code = attr.ib(
        validator=attr.validators.optional(attr.validators.instance_of(int)),
        default=None,
    )
    content_length = attr.ib(
        validator=attr.validators.optional(attr.validators.instance_of(int)),
        default=None,
    )
    content_type = attr.ib(
        validator=attr.validators.optional(attr.validators.instance_of(str)),
        default=None,
    )
    duration = attr.ib(
        validator=attr.validators.optional(attr.validators.instance_of(float)),
        default=None,
    )
    last_modified = attr.ib(
        validator=attr.validators.optional(attr.validators.instance_of(str)),
        default=None,
    )
    timeout = attr.ib(validator=attr.validators.instance_of(bool), default=False)
    connection_error = attr.ib(
        validator=attr.validators.instance_of(bool), default=False
    )


def get_service_urls(csv_path, col_no):
    with open(csv_path) as csv_file:
        reader = csv.reader(csv_file, delimiter="\t")
        return [r[col_no] for r in reader]


class Monitor:
    """
    Monitors a list of URL's using the provided check function.
    A check job is scheduled for each URL, then the scheduler main loop and
    each job execution are run in separate threads.

    Parameters:
        service_urls(list): URL's to monitor
        output_path(str): The path of the CSV file to append the results to.
        check_interval(float): Interval in seconds when each URL is to be checked.
        timeout(float): The timeout in seconds for the GET requests - if `None`,
            defaults to `DEFAULT_CHECK_INTERVAL`.
    """

    def __init__(
        self, service_urls, check_func, output_path, check_interval, timeout=None
    ):
        self.urls = service_urls
        self.check_func = check_func
        self.output_path = output_path
        self.check_interval = check_interval
        self.timeout = timeout or DEFAULT_CHECK_INTERVAL
        self.scheduler = ThreadedScheduler()
        self.csv_write_lock = threading.Lock()

    def schedule_jobs(self):
        """
        Schedules a job for each service URL.
        """
        for url_id, url in enumerate(self.urls):
            info(f"Scheduling check for {url} every {self.check_interval} seconds")
            self.scheduler.every(self.check_interval).seconds.do(
                run_threaded_job,
                partial(
                    self.check_func,
                    url=url,
                    url_id=url_id,
                    output_path=self.output_path,
                    csv_write_lock=self.csv_write_lock,
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
