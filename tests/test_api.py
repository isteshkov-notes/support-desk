import httpx
from fastapi.testclient import TestClient


def test_health_ok(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == httpx.codes.OK
    assert response.json() == {"status": "ok"}


# Go:
#   func TestHealthOK(t *testing.T) {
#       rec := get(t, "/health")
#       if rec.Code != http.StatusOK {
#           t.Fatalf("status = %d, want %d", rec.Code, http.StatusOK)
#       }
#       var body map[string]string
#       if err := json.NewDecoder(rec.Body).Decode(&body); err != nil {
#           t.Fatal(err)
#       }
#       if !maps.Equal(body, map[string]string{"status": "ok"}) {
#           t.Errorf("body = %v, want status=ok", body)
#       }
#   }
#
# A plain `assert` replaces each if/t.Fatalf: pytest rewrites it to print both sides
# on failure. A failing assert stops the test, like t.Fatal (there is no t.Error
# "keep going" mode). `==` on dicts compares contents, like maps.Equal / reflect.DeepEqual.


async def test_health_ok_async(async_client: httpx.AsyncClient) -> None:
    response = await async_client.get("/health")

    assert response.status_code == httpx.codes.OK
    assert response.json() == {"status": "ok"}


# Go: identical to TestHealthOK - Go has no async/sync split, every call can block.
#   resp, err := client.Get(srv.URL + "/health")
#   if err != nil { t.Fatal(err) }
#   defer resp.Body.Close()
#
# In Python `async_client.get(...)` only creates a coroutine (like a goroutine that
# hasn't started); `await` runs it and gives back the result. Forget the `await` and
# you get a coroutine object instead of a response - pyright strict reports it.


def test_unknown_route_is_404(client: TestClient) -> None:
    response = client.get("/nope")

    assert response.status_code == httpx.codes.NOT_FOUND


# Go:
#   func TestUnknownRouteIs404(t *testing.T) {
#       if rec := get(t, "/nope"); rec.Code != http.StatusNotFound {
#           t.Fatalf("status = %d, want %d", rec.Code, http.StatusNotFound)
#       }
#   }


def test_tools_endpoint_lists_definitions(client: TestClient) -> None:
    response = client.get("/tools")

    assert response.status_code == httpx.codes.OK
    names = [tool["name"] for tool in response.json()]
    assert names == ["get_customer", "lookup_order", "search_policies", "issue_refund"]


# Go:
#   rec := get(t, "/tools")
#   var defs []struct{ Name string `json:"name"` }
#   json.NewDecoder(rec.Body).Decode(&defs)
# response.json() returns untyped data (dicts/lists) - like decoding into `any`.
