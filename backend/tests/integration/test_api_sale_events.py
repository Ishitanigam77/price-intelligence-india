"""Integration tests for sale-event HTTP APIs."""

import uuid
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.domain.enums import SaleEventSource, SaleEventType
from tests.factories import (
    make_brand,
    make_category,
    make_retailer,
    make_sale_event,
)


def _seed_events(db_session: Session) -> dict[str, object]:
    now = datetime.now(UTC)
    retailer = make_retailer()
    brand = make_brand()
    category = make_category()
    db_session.add_all([retailer, brand, category])
    db_session.flush()
    past = make_sale_event(
        name="FIXTURE: Past National Shopping Event",
        event_type=SaleEventType.NATIONAL_SHOPPING,
        source=SaleEventSource.MANUAL_CURATION,
        start_date=now - timedelta(days=40),
        end_date=now - timedelta(days=35),
    )
    current = make_sale_event(
        name="FIXTURE: Current Category Sale",
        event_type=SaleEventType.CATEGORY,
        category=category,
        start_date=now - timedelta(hours=6),
        end_date=now + timedelta(days=2),
    )
    upcoming = make_sale_event(
        name="FIXTURE: Upcoming Seasonal Sale",
        event_type=SaleEventType.SEASONAL,
        start_date=now + timedelta(days=14),
        end_date=now + timedelta(days=21),
    )
    retailer_upcoming = make_sale_event(
        name="FIXTURE: Upcoming Retailer Sale",
        event_type=SaleEventType.RETAILER_SPECIFIC,
        retailer=retailer,
        start_date=now + timedelta(days=7),
        end_date=now + timedelta(days=10),
    )
    db_session.add_all([past, current, upcoming, retailer_upcoming])
    db_session.flush()
    return {
        "now": now,
        "retailer": retailer,
        "brand": brand,
        "category": category,
        "past": past,
        "current": current,
        "upcoming": upcoming,
        "retailer_upcoming": retailer_upcoming,
    }


def test_list_sale_events_returns_persisted_fixture_events(
    client: TestClient, db_session: Session
) -> None:
    seed = _seed_events(db_session)
    response = client.get("/api/v1/sale-events")
    assert response.status_code == 200
    body = response.json()
    names = [item["name"] for item in body["items"]]
    assert "FIXTURE: Past National Shopping Event" in names
    assert "FIXTURE: Current Category Sale" in names
    assert "FIXTURE: Upcoming Seasonal Sale" in names
    current = next(item for item in body["items"] if item["id"] == str(seed["current"].id))
    assert current["status"] == "during_event"
    assert current["event_type"] == "category"
    assert current["source"] == "manual_curation"
    upcoming = next(item for item in body["items"] if item["id"] == str(seed["upcoming"].id))
    assert upcoming["status"] == "before_event"
    past = next(item for item in body["items"] if item["id"] == str(seed["past"].id))
    assert past["status"] == "after_event"


def test_list_sale_events_filters_by_type_and_status(
    client: TestClient, db_session: Session
) -> None:
    _seed_events(db_session)
    typed = client.get("/api/v1/sale-events", params={"event_type": "seasonal"})
    assert typed.status_code == 200
    assert [item["event_type"] for item in typed.json()["items"]] == ["seasonal"]

    before = client.get("/api/v1/sale-events", params={"status": "before_event"})
    assert before.status_code == 200
    assert before.json()["total"] == 2
    assert all(item["status"] == "before_event" for item in before.json()["items"])


def test_upcoming_endpoint_excludes_current_and_past(
    client: TestClient, db_session: Session
) -> None:
    seed = _seed_events(db_session)
    response = client.get("/api/v1/sale-events/upcoming")
    assert response.status_code == 200
    body = response.json()
    names = [item["name"] for item in body["items"]]
    assert names == [
        "FIXTURE: Upcoming Retailer Sale",
        "FIXTURE: Upcoming Seasonal Sale",
    ]
    assert all(item["status"] == "before_event" for item in body["items"])

    filtered = client.get(
        "/api/v1/sale-events/upcoming",
        params={"retailer_id": str(seed["retailer"].id)},
    )
    assert [item["name"] for item in filtered.json()["items"]] == [
        "FIXTURE: Upcoming Retailer Sale"
    ]


def test_get_sale_event_and_unknown_id(client: TestClient, db_session: Session) -> None:
    seed = _seed_events(db_session)
    found = client.get(f"/api/v1/sale-events/{seed['past'].id}")
    assert found.status_code == 200
    assert found.json()["name"] == "FIXTURE: Past National Shopping Event"
    assert found.json()["status"] == "after_event"

    missing = client.get(f"/api/v1/sale-events/{uuid.uuid4()}")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "not_found"


def test_empty_sale_events_is_an_empty_page_not_fabricated_campaigns(
    client: TestClient,
) -> None:
    response = client.get("/api/v1/sale-events")
    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0, "limit": 50, "offset": 0}


def test_sale_calendar_maps_historical_families_without_inventing_announcements(
    client: TestClient, db_session: Session
) -> None:
    now = datetime.now(UTC)
    for year in (now.year - 2, now.year - 1):
        start = datetime(year, 3, 15, tzinfo=UTC)
        db_session.add(
            make_sale_event(
                name=f"FIXTURE: Mid-March Sale {year}",
                event_type=SaleEventType.SEASONAL,
                source=SaleEventSource.MANUAL_CURATION,
                start_date=start,
                end_date=start + timedelta(days=3),
            )
        )
    db_session.flush()
    response = client.get("/api/v1/sale-events/calendar")
    assert response.status_code == 200
    body = response.json()
    assert "not guaranteed retailer announcements" in body["disclaimer"].lower()
    assert body["total"] >= 1
    assert body["predicted"] is None if "predicted" in body else True
    item = body["items"][0]
    assert item["evidence_status"] in {"confirmed", "expected", "inferred", "unknown"}
    if item["evidence_status"] != "confirmed":
        assert item["mapping_method"] in {
            "fixed_calendar",
            "festival_relative",
            "recurring",
            "retailer_specific",
            "insufficient",
        }
