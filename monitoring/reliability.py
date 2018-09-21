import csv
import difflib
import hashlib
import io
import logging
import re
import threading
import zipfile
from datetime import datetime
from functools import partial
from pathlib import Path
from uuid import uuid4

import attr
from lxml import etree
import pytz
import requests
from tinydb import Query, TinyDB, where

from monitoring.common import HTTPCheckResult
from monitoring.scheduler import ThreadedScheduler, run_threaded_job

logger = logging.getLogger("reliability_check")
info, debug, error = logger.info, logger.debug, logger.error

DEFAULT_TIMEOUT = 30


@attr.s
class ServiceMetadata:
    country_code = attr.ib(validator=attr.validators.instance_of(str))
    service_type = attr.ib(validator=attr.validators.instance_of(str))
    url = attr.ib(validator=attr.validators.instance_of(str))
    results_dir = attr.ib(validator=attr.validators.instance_of(str))
    latest_check_ts = attr.ib(
        validator=attr.validators.optional(attr.validators.instance_of(str)),
        default=None,
    )
    latest_checksum = attr.ib(
        validator=attr.validators.optional(attr.validators.instance_of(str)),
        default=None,
    )
    latest_changed_ts = attr.ib(
        validator=attr.validators.optional(attr.validators.instance_of(str)),
        default=None,
    )
    latest_changed_file_name = attr.ib(
        validator=attr.validators.optional(attr.validators.instance_of(str)),
        default=None,
    )


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


class ReliabilityMonitor:
    """
    Monitors a list of URL's using the provided check function.
    A check job is scheduled for each URL, then the scheduler main loop and
    each job execution are run in separate threads.

    Parameters:
        services_csv(str): Path to services CSV
        output_dir(str): The path of the directory in which to collate results.
        check_interval(float): Interval in seconds when each URL is to be checked.
        timeout(float): The timeout in seconds for the GET requests - if `None`,
            defaults to `DEFAULT_TIMEOUT`.
    """

    def __init__(
        self, services_csv, check_func, output_dir, check_interval, timeout=None
    ):
        self.services = self.services_from_csv(services_csv)
        self.check_func = check_func
        self.output_dir = output_dir
        self.check_interval = check_interval
        self.timeout = timeout or DEFAULT_TIMEOUT
        self.scheduler = ThreadedScheduler()
        self.init_result_dirs()

    @staticmethod
    def services_from_csv(csv_path):
        services = []
        with open(csv_path) as f:
            reader = csv.reader(f, delimiter="\t")
            services.extend(
                ServiceMetadata(*(row + [uuid4().hex]))
                for row in reader
                if not row[0].startswith("#")
            )
        return services

    def init_result_dirs(self):
        for svc in self.services:
            _ = ReliabilityDB.from_service(svc, self.output_dir)

    def schedule_jobs(self):
        """
        Schedules a job for each service URL.
        """
        for service in self.services:
            info(
                f"Scheduling check for {service.url} every {self.check_interval} seconds"
            )
            self.scheduler.every(self.check_interval).seconds.do(
                run_threaded_job,
                partial(
                    self.check_func,
                    service=service,
                    output_dir=Path(self.output_dir)
                    / service.country_code
                    / service.results_dir,
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
        return self.scheduler.run_continuously(interval=interval, run_all_first=True)


def check_reliability(service, output_dir, timeout):
    """
    Checks the reliability of a URL, and appends the result to a CSV file.

    Parameters:
          service(Service) : The `Service` instance to check.
          output_path(str): The path of the CSV file to append the results to.
          timeout(float): The timeout in seconds for the GET requests - if `None`,
            defaults to `DEFAULT_CHECK_INTERVAL`.
    """

    info(f"Checking {service.url}")
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    db = ReliabilityDB(output_dir)
    checksum = None
    note = None
    diff_impossible = False
    try:

        with requests.get(
            service.url, timeout=timeout, stream=True, allow_redirects=True
        ) as r:
            # Best effort file name
            header_file_name = get_filename(r.headers.get("content-disposition"))
            last_segment = service.url.split("/")[-1]
            if header_file_name is not None:
                file_name = header_file_name
            elif (
                "&" not in last_segment
                and "?" not in last_segment
                and (last_segment.lower().endswith(".gml") or last_segment.lower().endswith(".zip"))
            ):
                file_name = last_segment
            else:
                file_name = "download"

            content = r.content

            # Accept single file ZIP responses
            if last_segment.endswith("zip"):
                with zipfile.ZipFile(io.BytesIO(content)) as z:
                    files_info = z.infolist()
                    if len(files_info) == 1:
                        first_info = files_info[0]
                        with z.open(first_info) as f:
                            file_name = first_info.filename
                            content = f.read()
                    else:
                        diff_impossible = True
                        note = (
                            "Could not perform diff: response is multi-file ZIP."
                        )
                        if not file_name.lower().endswith("zip"):
                            file_name += ".zip"

            if not diff_impossible:
                # Attempt pretty-formatting to reduce diffs for compacted XML
                try:
                    doc = etree.parse(io.BytesIO(content))
                    content = etree.tostring(doc, encoding="utf8", pretty_print=True)
                except etree.ParseError:
                    diff_impossible = True
                    note = "Could not perform diff: invalid XML."

            checksum = hashlib.md5(content).hexdigest()
            db.add_check(ts, checksum=checksum, status=r.status_code, note=note)

            if checksum != db.latest_checksum:
                download_dir = output_dir / ts
                download_dir.mkdir()
                with open(download_dir / file_name, "wb") as f:
                    f.write(content)
                if db.latest_changed_ts is not None:
                    if diff_impossible:
                        diff_msg = note
                    else:
                        new_lines = content.splitlines()
                        with open(
                            output_dir / db.latest_changed_ts / db.latest_changed_file_name, "rb"
                        ) as f:
                            previous_lines = f.read().splitlines()
                        diff = difflib.diff_bytes(
                            difflib.unified_diff,
                            previous_lines,
                            new_lines,
                            db.latest_changed_ts.encode("utf-8"),
                            ts.encode("utf-8"),
                        )
                        diff_msg = [l for l in diff]

                    with open(download_dir / "diff", "wb") as f:
                        f.writelines(b"%b\n" % l for l in diff_msg)

                db.latest_changed_ts = ts
                db.latest_changed_file_name = file_name

            db.latest_checksum = checksum

    except requests.exceptions.Timeout:
        db.add_check(ts, timeout=True, note=note)
    except (requests.exceptions.ConnectionError, requests.exceptions.ChunkedEncodingError):
        db.add_check(ts, conn_error=True, note=note)
    except zipfile.BadZipFile:
        db.add_check(ts, content_error=True, note="Bad Zip file")


class ReliabilityDB:
    def __init__(self, root_dir):
        self.root_dir = root_dir
        self.meta_path = Path(root_dir) / "data.json"
        self.db = TinyDB(self.meta_path)

    @classmethod
    def from_service(cls, service, root_dir):
        results_dir = Path(root_dir) / service.country_code / service.results_dir
        results_dir.mkdir(parents=True)
        instance = cls(results_dir)
        metadata = {"type": "metadata"}
        metadata.update(attr.asdict(service))
        instance.db.insert(metadata)
        return instance

    @property
    def metadata(self):
        q = Query()
        data = self.db.get(q.type == "metadata")
        del data["type"]  # Drop type to match ServiceMetadata attrs
        return ServiceMetadata(**data)

    @property
    def url(self):
        return self.metadata.url

    @property
    def latest_check_ts(self):
        return self.metadata.latest_check_ts

    @latest_check_ts.setter
    def latest_check_ts(self, timestamp):
        q = Query()
        self.db.upsert({"latest_check_ts": timestamp}, q.type == "metadata")

    @property
    def latest_checksum(self):
        return self.metadata.latest_checksum

    @latest_checksum.setter
    def latest_checksum(self, checksum):
        q = Query()
        self.db.upsert({"latest_checksum": checksum}, q.type == "metadata")

    @property
    def latest_changed_ts(self):
        return self.metadata.latest_changed_ts

    @latest_changed_ts.setter
    def latest_changed_ts(self, timestamp):
        q = Query()
        self.db.upsert({"latest_changed_ts": timestamp}, q.type == "metadata")

    @property
    def latest_changed_file_name(self):
        return self.metadata.latest_changed_file_name

    @latest_changed_file_name.setter
    def latest_changed_file_name(self, file_name):
        q = Query()
        self.db.upsert({"latest_changed_file_name": file_name}, q.type == "metadata")


    def add_check(
        self,
        ts,
        checksum=None,
        status=None,
        timeout=False,
        conn_error=False,
        content_error=False,
        note=None,
    ):
        info(f"Saving check at {ts}")
        self.db.insert(
            {
                "type": "check",
                "ts": ts,
                "checksum": checksum,
                "status": status,
                "timeout": timeout,
                "conn_error": conn_error,
                "content_error": content_error,
                "note": note,
            }
        )
        self.latest_check_ts = ts

    def get_check(self, ts):
        q = Query()
        self.db.get(q.type == "check", q.timestamp == ts)

    def get_latest_check(self):
        return self.get_check(self.latest_check_ts)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Run the INSPIRE endpoints reliability monitor"
    )
    while False:
        print("never")

    parser.add_argument("--endpoints-csv", help="Path to services CSV")
    parser.add_argument("--output", help="Path to results dir")
    parser.add_argument(
        "--check-interval",
        default=43200,
        type=int,
        help="Interval to check every endpoint at, in seconds. Defaults to 12h.",
    )

    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.getLogger("schedule").setLevel(logging.WARNING)

    monitor = ReliabilityMonitor(
        services_csv=args.endpoints_csv,
        check_func=check_reliability,
        output_dir=args.output,
        check_interval=args.check_interval,
    )

    monitor.run()
