import asyncio
from pathlib import Path

import pytest

from pcb2stl import config, runner, worker
from pcb2stl.domain import ConversionParams
from pcb2stl.runner import ConversionTimeout, OverloadError, offload

GERBER = (Path(__file__).resolve().parents[1] / "fixtures" / "sample.gbr").read_bytes()


@pytest.fixture(autouse=True)
def _real_pool(monkeypatch):
    monkeypatch.setattr(config, "INLINE", False)


@pytest.fixture(scope="module", autouse=True)
def _shutdown_pool():
    yield
    runner.stop_pool()


def test_offload_runs_the_conversion_in_a_worker_process():
    stl = asyncio.run(offload(worker.convert_job, "board.gbr", GERBER, ConversionParams(height_mm=0.2)))
    assert isinstance(stl, (bytes, bytearray)) and len(stl) > 0


def test_hard_timeout_kills_the_worker_and_raises(monkeypatch):
    monkeypatch.setattr(config, "CONVERT_TIMEOUT_S", 0.2)
    with pytest.raises(ConversionTimeout):
        asyncio.run(offload(worker.sleep, 5.0))


def test_concurrency_cap_sheds_excess_load_with_overload(monkeypatch):
    monkeypatch.setattr(config, "MAX_CONCURRENT", 1)

    async def two():
        return await asyncio.gather(
            offload(worker.convert_job, "a.gbr", GERBER, ConversionParams()),
            offload(worker.convert_job, "b.gbr", GERBER, ConversionParams()),
            return_exceptions=True,
        )

    results = asyncio.run(two())
    assert sum(isinstance(r, OverloadError) for r in results) == 1
    assert any(isinstance(r, (bytes, bytearray)) for r in results)
