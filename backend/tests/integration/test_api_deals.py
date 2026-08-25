"""Integration test for `/api/v1/deals`: Phase 2 is a foundation-only, always-empty route.

Deal detection depends on price-drop detection (Phase 4) and sale-event intelligence (Phase 7),
neither of which exist yet — this test only pins down that the route exists, is well-typed, and
never fabricates a "deal".
"""

from fastapi.testclient import TestClient


def test_list_deals_is_always_an_empty_page(client: TestClient) -> None:
    response = client.get("/api/v1/deals")
    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0, "limit": 50, "offset": 0}


def test_list_deals_respects_pagination_params_even_though_empty(client: TestClient) -> None:
    response = client.get("/api/v1/deals", params={"limit": 10, "offset": 5})
    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0, "limit": 10, "offset": 5}
