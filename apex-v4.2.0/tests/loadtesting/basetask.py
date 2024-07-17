from abc import ABCMeta, abstractmethod

import trio


class LoadTestBaseTask(metaclass=ABCMeta):
    def __init__(self) -> None:
        pass

    @abstractmethod
    async def setup(self, *, nursery: trio.Nursery, **kwargs) -> None:
        pass

    @abstractmethod
    async def __call__(self, *, nursery: trio.Nursery, **kwargs) -> None:
        pass

    @abstractmethod
    def analyze(self, scenario_id: int) -> None:
        pass
