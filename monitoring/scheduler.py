import time
import logging
import datetime
import threading
import schedule


logger = logging.getLogger("schedule")


class ThreadedScheduler(schedule.Scheduler):
    """
    Custom `Scheduler` that:
     - executed the scheduler loop in its own thread (accepts poison pill).
     - catches job exceptions, as per https://gist.github.com/mplewis/8483f1c24f2d6259aef6
    """

    def __init__(self, reschedule_on_failure=True):
        """
        If reschedule_on_failure is True, jobs will be rescheduled for their
        next run as if they had completed successfully. If False, they'll run
        on the next run_pending() tick.
        """
        self.reschedule_on_failure = reschedule_on_failure
        super().__init__()

    def _run_job(self, job):
        try:
            super()._run_job(job)
        except Exception:
            logger.exception("Scheduled job exception: ")
            job.last_run = datetime.datetime.now()
            job._schedule_next_run()

    def run_continuously(self, interval=1):
        stop_continuous_run = threading.Event()

        class ScheduleThread(threading.Thread):
            @classmethod
            def run(cls):
                while not stop_continuous_run.is_set():
                    self.run_pending()
                    time.sleep(interval)

        scheduler_thread = ScheduleThread()
        scheduler_thread.start()
        return stop_continuous_run


threaded_scheduler = ThreadedScheduler()
jobs = threaded_scheduler.jobs


def run_threaded_job(job):
    job_thread = threading.Thread(target=job)
    job_thread.start()
    return job_thread

