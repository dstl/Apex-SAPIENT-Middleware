import json
import platform
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Optional

import click
import trio
from sqlalchemy import insert

from tests.loadtesting.apex_subprocess import apex_config, apex_subprocess
from tests.loadtesting.loading import loadtest_runner
from tests.loadtesting.registration import LoadTestTaskRegistration
from tests.loadtesting.schema import Scenario, get_engine
from tests.loadtesting.testing import LoadTestTask


@click.group()
def main():
    pass


@main.command(
    help="""\
        Load-testing the load-tester.

        Launches simple tasks where each task logs it's start time,
        sleeps for a given amount of time, and then logs it's end-time.
        The tests prints stats related to whether the load-tester launches
        the tasks at the expected rate.
        """
)
@click.option("--tasks-per-sec", default=5.0, help="How fast to launch new tasks")
@click.option("--duration", default=10.0, help="Duration of the load-testing trial in seconds")
@click.option("--max-tasks", default=10, help="Max number of tasks")
@click.option(
    "--delay-start", default=10.0, help="Delay to the start of the load testing in seconds"
)
@click.option("--task-sleep-time", default=10.0, help="Amount of time each task sleeps")
def test(
    tasks_per_sec: float,
    duration: float,
    max_tasks: int,
    delay_start: float,
    task_sleep_time: float,
):
    task = LoadTestTask(task_sleep_time)

    async def trial():
        await loadtest_runner(
            scenario=task,
            scenarii_per_sec=tasks_per_sec,
            duration_s=duration,
            max_scenarii=max_tasks,
            delay_start_s=delay_start,
        )

    trio.run(trial)

    task.analyze(0)


@main.command(
    help="""\
        Child(ASM) node registration and heartbeat.

        Launches child nodes at a given rate, where each child will send a single
        registration message and any number of status report.
        There is only one peer(Fusion) node on the receiving end.

        Messages (registration, registration acknowledgment, status report) are
        logged on the send and reception side to a database.
        """
)
@click.option("--tasks-per-sec", default=5.0, help="How fast to launch new tasks")
@click.option("--duration", default=10.0, help="Duration of the load-testing trial in seconds")
@click.option("--max-tasks", default=10, help="Max number of tasks")
@click.option(
    "--delay-start",
    default=0.3,
    help=(
        "Delay to the start of the load testing in seconds. "
        "Helps with any sort of setup that may be required, e.g. running apex."
    ),
)
@click.option(
    "--apex-hostname",
    default=None,
    help="Hostname to a running instance of apex. If not given, an instance is created.",
)
@click.option("--child-port", default=5001)
@click.option("--peer-port", default=5002)
@click.option("--heartbeat-interval", default=1, help="Interval between heartbeats per second")
@click.option("--database", default=None, help="Path to the databases of messages")
@click.option(
    "--scenario-name", default="registration", help="Scenario name stored in the database"
)
@click.option(
    "--working-directory",
    default=None,
    help="directory where files are saved",
    required=platform.system() == "Windows",
)
@click.option(
    "--scenario-id", default=None, help="If given, only shows output without rerunning experiment"
)
@click.option(
    "--cli-figures/--no-cli-figures",
    default=False,
    help=(
        "Plot message latencies on the command-line using unicode. "
        "Might not work with all setups."
    ),
)
def registration(
    tasks_per_sec: float,
    duration: float,
    max_tasks: int,
    delay_start: float,
    apex_hostname: Optional[str],
    child_port: int,
    peer_port: int,
    heartbeat_interval: float,
    database: str,
    scenario_name: str,
    working_directory: Path,
    scenario_id: Optional[int],
    cli_figures: bool,
):
    if working_directory is None:
        temp_dir = TemporaryDirectory()
        working_directory = Path(temp_dir.name)
    else:
        working_directory = Path(working_directory)
        temp_dir = None

    working_directory.mkdir(parents=True, exist_ok=True)

    database = database or str((working_directory / "loadtesting.sql").absolute())

    task = LoadTestTaskRegistration(
        database=database,
        apex_hostname=apex_hostname or "127.0.0.1",
        child_port=child_port,
        peer_port=peer_port,
        heartbeat_interval_s=heartbeat_interval,
    )

    if scenario_id is None:
        scenario_id = scenario_to_database(
            database=database,
            scenario_name=scenario_name,
            tasks_per_sec=tasks_per_sec,
            duration=duration,
            max_tasks=max_tasks,
            delay_start=delay_start,
            parameters=task.parameters,
        )

        async def trial():
            await loadtest_runner(
                scenario=task,
                scenarii_per_sec=tasks_per_sec,
                duration_s=duration,
                max_scenarii=max_tasks,
                delay_start_s=delay_start,
                scenario_id=scenario_id,
            )

        try:
            with apex_subprocess(
                directory=working_directory,
                configuration=apex_config(child_port, peer_port),
                is_external=bool(apex_hostname is not None and apex_hostname.strip() != ""),
            ):
                trio.run(trial)
        finally:
            if temp_dir is not None:
                temp_dir.cleanup()

    task.analyze(scenario_id)
    if cli_figures:
        task.plot_cli_figure(scenario_id)


def scenario_to_database(
    database: str,
    scenario_name: str,
    tasks_per_sec: float,
    duration: float,
    max_tasks: int,
    delay_start: float,
    parameters: dict,
) -> int:
    with get_engine(database).connect() as connection, connection.begin():
        result = connection.execute(
            insert(Scenario).values(
                {
                    "name": scenario_name,
                    "tasks_per_sec": tasks_per_sec,
                    "duration": duration,
                    "max_tasks": max_tasks,
                    "delay_start": delay_start,
                    "parameters": json.dumps(parameters),
                }
            )
        )
        if result.inserted_primary_key is None:
            raise RuntimeError("could not get scenario id")
        (scenario_id,) = result.inserted_primary_key
        assert isinstance(scenario_id, int)
        return scenario_id


if __name__ == "__main__":
    main()
