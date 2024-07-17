from collections import Counter
from math import sqrt
from queue import SimpleQueue
from time import time_ns

import trio

from tests.loadtesting.basetask import LoadTestBaseTask


class LoadTestTask(LoadTestBaseTask):
    def __init__(self, task_sleep_time: float = 2) -> None:
        self.task_sleep_time = task_sleep_time
        self.start_logger: SimpleQueue[int] = SimpleQueue()
        self.end_logger: SimpleQueue[int] = SimpleQueue()

    async def setup(self, **_) -> None:
        pass

    async def __call__(self, **_) -> None:
        self.start_logger.put_nowait(time_ns())
        await trio.sleep(self.task_sleep_time)
        self.end_logger.put_nowait(time_ns())

    def analyze(self, scenario_id: int) -> None:
        def drain(queue) -> list[int]:
            times = []
            while not queue.empty():
                times.append(queue.get_nowait())
            return times

        def task_stats(times) -> tuple[float, float]:
            times = sorted(times)
            diffs = list(s - l for s, l in zip(times[1:], times[:-1]))
            avg = sum(diffs) / len(diffs)
            stddev = sqrt(sum((x - avg) * (x - avg) for x in diffs) / len(diffs))

            return avg * 1e-9, stddev * 1e-9

        def tasks_per_seconds(times):
            times = sorted(times)
            times = [int((u - times[0]) * 1e-9) for u in times]
            histogram = list(Counter(times).values())
            avg = sum(histogram) / len(histogram)
            stddev = sqrt(sum((x - avg) * (x - avg) for x in histogram) / len(histogram))
            return avg, stddev

        start_times = drain(self.start_logger)
        avg, stddev = task_stats(start_times)
        print("Stats for start times")
        print(f" -- average for |t(i+1) - t(i)|: {avg}")
        print(f" -- stddev for |t(i+1) - t(i)|: {stddev}")
        avg, stddev = tasks_per_seconds(start_times)
        print(f" -- average tasks per seconds: {avg}")
        print(f" -- stddev of tasks per seconds: {stddev}")

        end_times = drain(self.end_logger)
        avg, stddev = task_stats(end_times)
        print("\nStats for end time from previous task")
        print(f" -- average for |t(i+1) - t(i)|: {avg}")
        print(f" -- stddev for |t(i+1) - t(i)|: {stddev}")
        avg, stddev = tasks_per_seconds(end_times)
        print(f" -- average tasks per seconds: {avg}")
        print(f" -- stddev of tasks per seconds: {stddev}")
