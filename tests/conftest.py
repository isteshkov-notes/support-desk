from collections.abc import AsyncIterator
from datetime import UTC, datetime

import httpx
import pytest
from fastapi.testclient import TestClient

from supportdesk.main import app
from supportdesk.repository import InMemoryRepository
from supportdesk.tools import ToolContext, ToolRegistry, default_registry

# conftest.py is loaded by pytest automatically; its fixtures are visible to every test
# in this folder without imports. A test gets a fixture by naming it as a parameter.

FIXED_NOW = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)
# The fixtures' "today". O-5009 was delivered exactly 31 days before this (spec edge case).


@pytest.fixture
def repo() -> InMemoryRepository:
    return InMemoryRepository.from_data()


# Go:
#   func newRepo(t *testing.T) *InMemoryRepository {
#       t.Helper()
#       r, err := NewInMemoryRepositoryFromFS(defaultData)
#       if err != nil { t.Fatal(err) }
#       return r
#   }
# A fresh repository per test: issue_refund mutates it, so tests can't leak into each
# other (fixtures default to scope="function").


@pytest.fixture
def ctx(repo: InMemoryRepository) -> ToolContext:
    return ToolContext(repo=repo, now=lambda: FIXED_NOW)


# Go:
#   ctx := ToolContext{Repo: newRepo(t), Now: func() time.Time { return fixedNow }}
# Fixtures can depend on fixtures: pytest builds `repo` first and passes it in.
# `lambda: FIXED_NOW` is an anonymous func() time.Time - the frozen clock.


@pytest.fixture
def registry() -> ToolRegistry:
    return default_registry()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


# Go (a test helper; no real server, the handler is called in memory):
#   func get(t *testing.T, path string) *httptest.ResponseRecorder {
#       t.Helper()
#       rec := httptest.NewRecorder()
#       app.ServeHTTP(rec, httptest.NewRequest(http.MethodGet, path, nil))
#       return rec
#   }
#
# Difference: in Go you call the helper yourself; pytest calls the fixture for you
# because the test has a parameter named `client`. A new one is made for every test.


@pytest.fixture
async def async_client() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# Go:
#   func newClient(t *testing.T) *http.Client {
#       srv := httptest.NewServer(app)
#       t.Cleanup(srv.Close)        // == everything after `yield`
#       return srv.Client()
#   }
#
# `yield c` hands the client to the test and pauses here; when the test ends (pass or
# fail) execution resumes, the `async with` block exits and the client is closed.
# That is t.Cleanup. `async with` is like `defer c.Close()` for a resource whose
# open/close are themselves async. Unlike httptest.NewServer, ASGITransport opens no
# socket: requests go straight into the app in memory.
