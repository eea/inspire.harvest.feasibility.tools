from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin
import requests
import logme
import pytz
import time

log = logme.log(scope="module", name="inspire_qa")

DEFAULT_TIMEOUT = 10


class ETFTestRunner:
    """
    Test running interface to the ETF API.
    """

    def __init__(self, api_url, timeout=DEFAULT_TIMEOUT):
        self.api_url = api_url
        self.timeout = timeout

    def upload_test_data(self, path):
        """
        Upload a test data file.
        Args:
            path: Location of the file to upload.
                File name must NOT contain multiple dots.
        Returns:
            The test object id, e.g. 'EID81c259d0-6b4f-4beb-910b-93cc2253bf70'
        """
        url = urljoin(self.api_url, "TestObjects")
        path = Path(path).resolve()
        files = {"file": (path.name, open(path, "rb"), "text/xml")}
        log.info(f"Uploading file {str(path)} to ETF")
        upload_id = None
        try:
            response = requests.post(url, params={"action": "upload"}, files=files, timeout=self.timeout)
            upload_id = response.json().get("testObject", {}).get("id")
        except requests.Timeout:
            log.error(f"Could not upload {str(path)} to ETF - timed out")
        except ValueError:
            log.error(f"Could not upload {str(path)} to ETF")

        if upload_id is None:
            log.error(f"Could not upload {str(path)} to ETF - did not receive TestObject ID.")
        else:
            log.info(f"ETF issued upload id {upload_id} for file {str(path)}")
        return upload_id

    def run_test(self, test_id, test_file_path, label):
        """
        Start a test run.
        Args:
            test_id:
            test_file_path:
            label:
        Returns:
            Id of started test.
        """
        file_upload_id = self.upload_test_data(test_file_path)

        if file_upload_id is None:
            log.error("Could not upload file to ETF")
            return None

        payload = {
            "label": label,
            "executableTestSuiteIds": [test_id],
            "arguments": {"files_to_test": ".*", "tests_to_execute": ".*"},
            "testObject": {"id": file_upload_id},
        }

        url = urljoin(self.api_url, "TestRuns")
        run_id = None
        try:
            log.info(
                f"Starting test {test_id} on uploaded file {test_file_path} [{file_upload_id}]"
            )
            response = requests.post(url, json=payload, timeout=self.timeout).json()
            run_id = (
                response.get("EtfItemCollection", {})
                .get("testRuns", {})
                .get("TestRun", {})
                .get("id")
            )
            log.info(f"ETF test {test_id} started with run id {run_id}")

        except requests.Timeout:
            log.error(f"Could not start test run on ETF - timed out")
        except ValueError:
            log.error(f"Could not start test run on ETF")

        return run_id

    def get_run_progress(self, run_id):
        """Returns a test run's progress as a float (0.0 - 1.0)."""
        url = urljoin(self.api_url, f"TestRuns/{run_id}/progress")
        try:
            response = requests.get(url, timeout=self.timeout).json()
            progress = float(response["val"]) / float(response["max"])
            log.info(f"Progress on ETF test run {run_id}: {progress * 100:.2f}%")

        except requests.Timeout:
            log.error(f"Could not get ETF run {run_id} progress - timed out")
            progress = None
        except ValueError:
            log.error(f"Could not get ETF run {run_id} progress.")
            progress = None

        return progress

    def delete_run(self, run_id):
        """Asks ETF to delete a test run."""
        url = urljoin(self.api_url, f"TestRuns/{run_id}")
        response = requests.delete(url)
        if response.status_code == 204:
            log.info(f"ETF test run {run_id} deleted.")
        else:
            log.error(f"Could not delete ETF test run {run_id}.")

    def run_ended(self, run_id):
        """Returns `True` if the run has ended."""
        progress = self.get_run_progress(run_id)
        if progress is None:
            return None
        return progress == 1.0

    def get_run_report(self, run_id):
        """Returns the run report as a dict."""
        url = urljoin(self.api_url, f"TestRuns/{run_id}")

        report = None
        try:
            report = requests.get(url).json()
        except requests.Timeout:
            log.error(f"Could not get report for ETF test run {run_id} - timed out.")
        except ValueError:
            log.error(f"Could not get report for ETF test run {run_id}.")

        return report

    def save_html_run_report(self, run_id):
        """Saves a test run's HTML report to file."""
        report_file_name = f"{run_id}.html"
        url = urljoin(self.api_url, f"TestRuns/{report_file_name}")
        response = requests.get(url)
        with open(report_file_name, "wb") as f:
            f.write(response.content)
        log.info(f"Report saved to {report_file_name}")

    def run_passed(self, run_id):
        """Returns `True` if the test run has passed."""
        report = self.get_run_report(run_id)
        if report is None:
            return False
        status = (
            report.get("EtfItemCollection", {})
            .get("testRuns", {})
            .get("TestRun", {})
            .get("status", "")
        )
        return status.startswith("PASSED")


def check_md_conformance(etf_url, md_path, check_interval=1, timeout=300):
    dl_md_conformance_test_id = "EID9a31ecfc-6673-43c0-9a31-b4595fb53a98"
    dl_md_conformance_test_label_template = (
        "Test run on {} with test suite " "Conformance class: Metadata for interoperability"
    )

    etf_test_runner = ETFTestRunner(etf_url)
    ts = datetime.utcnow().replace(tzinfo=pytz.UTC).isoformat()
    label = dl_md_conformance_test_label_template.format(ts)
    run_id = etf_test_runner.run_test(
        test_id=dl_md_conformance_test_id,
        test_file_path=md_path,
        label=label,
    )

    has_passed = False
    timed_out = False
    if run_id is not None:
        start_time = time.time()
        while True:
            if time.time() - start_time >= timeout:
                timed_out = True
                log.error(f"ETF run timed out after {timeout} seconds, stopping test.")
                etf_test_runner.delete_run(run_id)
                break
            has_ended = etf_test_runner.run_ended(run_id)
            if has_ended is None:
                log.error(f"Could not get ETF run {run_id} status, stopping test.")
                etf_test_runner.delete_run(run_id)
                break
            if has_ended:
                break
            time.sleep(check_interval)

        has_passed = etf_test_runner.run_passed(run_id)
    else:
        log.error("Could not start a test run on ETF")

    msg = "CHECK: Conformance of metadata for interoperability:"
    if not has_passed:
        if run_id is not None and not timed_out:
            etf_test_runner.save_html_run_report(run_id)
        log.error(f"{msg} FAILED")
    else:
        log.info(f"{msg} PASSED")

    return has_passed
