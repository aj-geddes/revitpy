"""Persistence through IUnitOfWork for RevitContext and AsyncRevitContext."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from revitpy.orm.context import RevitContext
from revitpy.orm.exceptions import AsyncOperationError, ORMException


class RecordingUnitOfWork:
    def __init__(self, fail: bool = False, sync_only: bool = False) -> None:
        self.log: list[str] = []
        self.fail = fail
        if sync_only:
            self.commit_async = None  # type: ignore[assignment]
            self.rollback_async = None  # type: ignore[assignment]

    def register_new(self, entity: Any) -> None:
        self.log.append("new")

    def register_dirty(self, entity: Any) -> None:
        self.log.append("dirty")

    def register_removed(self, entity: Any) -> None:
        self.log.append("removed")

    def register_clean(self, entity: Any) -> None:
        self.log.append("clean")

    def commit(self) -> None:
        if self.fail:
            raise RuntimeError("disk full")
        self.log.append("commit")

    def rollback(self) -> None:
        self.log.append("rollback")

    async def commit_async(self) -> None:
        if self.fail:
            raise RuntimeError("disk full")
        self.log.append("commit_async")

    async def rollback_async(self) -> None:
        self.log.append("rollback_async")


PROVIDER = SimpleNamespace(
    get_all_elements=lambda: [],
    get_elements_of_type=lambda _t: [],
    get_element_by_id=lambda _i: None,
)


def context_with(uow: RecordingUnitOfWork | None) -> RevitContext:
    return RevitContext(PROVIDER, unit_of_work=uow)


class TestSyncSave:
    def test_registers_and_commits(self) -> None:
        uow = RecordingUnitOfWork()
        ctx = context_with(uow)
        ctx.add(SimpleNamespace(id=1, name="a"))
        assert ctx.save_changes() == 1
        assert uow.log == ["new", "commit"]
        assert not ctx.has_changes

    def test_failure_rolls_back(self) -> None:
        uow = RecordingUnitOfWork(fail=True)
        ctx = context_with(uow)
        ctx.add(SimpleNamespace(id=1, name="a"))
        with pytest.raises(ORMException):
            ctx.save_changes()
        assert uow.log == ["new", "rollback"]

    def test_transaction_failure_rolls_back_unit_of_work(self) -> None:
        uow = RecordingUnitOfWork()
        ctx = context_with(uow)
        with pytest.raises(RuntimeError):
            with ctx.transaction():
                ctx.add(SimpleNamespace(id=1, name="a"))
                raise RuntimeError("boom")
        assert uow.log == ["rollback"]
        assert not ctx.has_changes


class TestAsyncSave:
    async def test_registers_and_commits_async(self) -> None:
        uow = RecordingUnitOfWork()
        ctx = context_with(uow)
        ctx.add(SimpleNamespace(id=1, name="a"))
        ctx.remove(SimpleNamespace(id=2, name="b"))
        actx = ctx.as_async()
        assert await actx.save_changes_async() == 2
        assert sorted(uow.log[:-1]) == ["new", "removed"]
        assert uow.log[-1] == "commit_async"
        assert not actx.has_changes

    async def test_uses_sync_commit_when_no_async(self) -> None:
        uow = RecordingUnitOfWork(sync_only=True)
        ctx = context_with(uow)
        ctx.add(SimpleNamespace(id=1, name="a"))
        assert await ctx.as_async().save_changes_async() == 1
        assert uow.log == ["new", "commit"]

    async def test_failure_rolls_back_and_keeps_changes(self) -> None:
        uow = RecordingUnitOfWork(fail=True)
        ctx = context_with(uow)
        ctx.add(SimpleNamespace(id=1, name="a"))
        actx = ctx.as_async()
        with pytest.raises(AsyncOperationError):
            await actx.save_changes_async()
        assert uow.log == ["new", "rollback_async"]
        assert actx.has_changes

    async def test_without_unit_of_work_only_accepts(self) -> None:
        ctx = context_with(None)
        ctx.add(SimpleNamespace(id=1, name="a"))
        actx = ctx.as_async()
        assert await actx.save_changes_async() == 1
        assert not actx.has_changes
