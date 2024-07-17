import trio

from tests.loadtesting.basetask import LoadTestBaseTask


async def loadtest_runner(
    scenario: LoadTestBaseTask,
    duration_s: float = 10,
    scenarii_per_sec: float = 10,
    max_scenarii: int = 100,
    delay_start_s: float = 0.5,
    **kwargs,
):
    start_time = trio.current_time() + delay_start_s
    nbscenarii = min(int(scenarii_per_sec * duration_s + 0.5), max_scenarii)
    start_times = [float(i) / scenarii_per_sec + start_time for i in range(nbscenarii)]

    async def task(start: float, nursery: trio.Nursery):
        await trio.sleep_until(start)
        await scenario(nursery=nursery, **kwargs)

    setup_time_s = 5
    with trio.move_on_after(delay_start_s + 1 + setup_time_s + duration_s):
        async with trio.open_nursery() as nursery:
            with trio.fail_after(setup_time_s):
                await scenario.setup(nursery=nursery, **kwargs)

            for i, start in enumerate(start_times):
                nursery.start_soon(task, start, nursery, name=f"task-{i}")
