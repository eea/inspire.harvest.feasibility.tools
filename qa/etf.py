from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin
import requests
import logme
import pytz
import time

log = logme.log(scope="module", name="inspire_qa")


class ETFTestRunner:
    """
    Test running interface to the ETF API.
    """

    def __init__(self, api_url):
        self.api_url = api_url

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
            response = requests.post(url, params={"action": "upload"}, files=files)
            upload_id = response.json().get("testObject", {}).get("id")
        except ValueError:
            log.error(f"Could not upload {str(path)} to ETF")

        log.info(f"EFT issued upload id {upload_id} for file {str(path)}")
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
        payload = {
            "label": label,
            "executableTestSuiteIds": [test_id],
            "arguments": {"files_to_test": ".*", "tests_to_execute": ".*"},
            "testObject": {"id": file_upload_id},
        }

        url = urljoin(self.api_url, "TestRuns")
        response = requests.post(url, json=payload).json()
        log.info(
            f"Starting test {test_id} on uploaded file {test_file_path} [{file_upload_id}]"
        )
        run_id = (
            response.get("EtfItemCollection", {})
            .get("testRuns", {})
            .get("TestRun", {})
            .get("id")
        )
        log.info(f"Test {test_id} started with run id {run_id}")
        return run_id

    def get_run_progress(self, run_id):
        """Returns a test run's progress as a float (0.0 - 1.0)."""
        url = urljoin(self.api_url, f"TestRuns/{run_id}/progress")
        response = requests.get(url).json()
        progress = float(response["val"]) / float(response["max"])
        log.info(f"Progress on test {run_id}: {progress * 100:.2f}%")
        return progress

    def run_ended(self, run_id):
        """Returns `True` if the run has ended."""
        return self.get_run_progress(run_id) == 1.0

    def get_run_report(self, run_id):
        """Returns the run report as a dict."""
        url = urljoin(self.api_url, f"TestRuns/{run_id}")
        return requests.get(url).json()

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
        status = (
            report.get("EtfItemCollection", {})
            .get("testRuns", {})
            .get("TestRun", {})
            .get("status")
        )
        return status != "FAILED"


def check_md_conformance(etf_url, md_path, check_interval=1):
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
    while not etf_test_runner.run_ended(run_id):
        time.sleep(check_interval)

    has_passed = etf_test_runner.run_passed(run_id)
    msg = "CHECK: Conformance of metadata for interoperability:"

    if not has_passed:
        log.error(f"{msg} FAILED")
        etf_test_runner.save_html_run_report(run_id)
    else:
        log.info(f"{msg} PASSED")

    return has_passed
