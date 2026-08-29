"""Repository for `SaleEvent`."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Select, func, or_, select

from app.db.models.sale_event import SaleEvent
from app.domain.enums import SaleEventSource, SaleEventStatus, SaleEventType
from app.repositories.base import BaseRepository


class SaleEventRepository(BaseRepository[SaleEvent]):
    model = SaleEvent

    def list_filtered(
        self,
        *,
        event_type: SaleEventType | None = None,
        source: SaleEventSource | None = None,
        retailer_id: uuid.UUID | None = None,
        category_id: uuid.UUID | None = None,
        brand_id: uuid.UUID | None = None,
        status: SaleEventStatus | None = None,
        at: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[SaleEvent]:
        stmt = self._filtered_stmt(
            event_type=event_type,
            source=source,
            retailer_id=retailer_id,
            category_id=category_id,
            brand_id=brand_id,
            status=status,
            at=at,
        )
        stmt = (
            stmt.order_by(SaleEvent.start_date.asc(), SaleEvent.id.asc())
            .limit(limit)
            .offset(offset)
        )
        return list(self.session.scalars(stmt).all())

    def count_filtered(
        self,
        *,
        event_type: SaleEventType | None = None,
        source: SaleEventSource | None = None,
        retailer_id: uuid.UUID | None = None,
        category_id: uuid.UUID | None = None,
        brand_id: uuid.UUID | None = None,
        status: SaleEventStatus | None = None,
        at: datetime | None = None,
    ) -> int:
        stmt = self._filtered_stmt(
            event_type=event_type,
            source=source,
            retailer_id=retailer_id,
            category_id=category_id,
            brand_id=brand_id,
            status=status,
            at=at,
        )
        count_stmt = select(func.count()).select_from(stmt.subquery())
        return int(self.session.scalar(count_stmt) or 0)

    def list_upcoming(
        self,
        *,
        at: datetime,
        retailer_id: uuid.UUID | None = None,
        category_id: uuid.UUID | None = None,
        brand_id: uuid.UUID | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[SaleEvent]:
        return self.list_filtered(
            retailer_id=retailer_id,
            category_id=category_id,
            brand_id=brand_id,
            status=SaleEventStatus.BEFORE_EVENT,
            at=at,
            limit=limit,
            offset=offset,
        )

    def count_upcoming(
        self,
        *,
        at: datetime,
        retailer_id: uuid.UUID | None = None,
        category_id: uuid.UUID | None = None,
        brand_id: uuid.UUID | None = None,
    ) -> int:
        return self.count_filtered(
            retailer_id=retailer_id,
            category_id=category_id,
            brand_id=brand_id,
            status=SaleEventStatus.BEFORE_EVENT,
            at=at,
        )

    def list_applicable_to_product(
        self,
        *,
        brand_id: uuid.UUID | None,
        category_id: uuid.UUID | None,
    ) -> list[SaleEvent]:
        """Events whose optional brand/category scope matches the product.

        Retailer-specific events are included; callers filter observations per retailer.
        """
        stmt = select(SaleEvent)
        if brand_id is None:
            stmt = stmt.where(SaleEvent.brand_id.is_(None))
        else:
            stmt = stmt.where(or_(SaleEvent.brand_id.is_(None), SaleEvent.brand_id == brand_id))
        if category_id is None:
            stmt = stmt.where(SaleEvent.category_id.is_(None))
        else:
            stmt = stmt.where(
                or_(SaleEvent.category_id.is_(None), SaleEvent.category_id == category_id)
            )
        stmt = stmt.order_by(SaleEvent.start_date.asc(), SaleEvent.id.asc())
        return list(self.session.scalars(stmt).all())

    def _filtered_stmt(
        self,
        *,
        event_type: SaleEventType | None,
        source: SaleEventSource | None,
        retailer_id: uuid.UUID | None,
        category_id: uuid.UUID | None,
        brand_id: uuid.UUID | None,
        status: SaleEventStatus | None,
        at: datetime | None,
    ) -> Select[tuple[SaleEvent]]:
        stmt: Select[tuple[SaleEvent]] = select(SaleEvent)
        if event_type is not None:
            stmt = stmt.where(SaleEvent.event_type == event_type)
        if source is not None:
            stmt = stmt.where(SaleEvent.source == source)
        if retailer_id is not None:
            stmt = stmt.where(SaleEvent.retailer_id == retailer_id)
        if category_id is not None:
            stmt = stmt.where(SaleEvent.category_id == category_id)
        if brand_id is not None:
            stmt = stmt.where(SaleEvent.brand_id == brand_id)
        if status is not None:
            if at is None:
                raise ValueError(
                    "A comparison time is required when filtering by sale-event status."
                )
            stmt = self._apply_status(stmt, status=status, at=at)
        return stmt

    @staticmethod
    def _apply_status(
        stmt: Select[tuple[SaleEvent]],
        *,
        status: SaleEventStatus,
        at: datetime,
    ) -> Select[tuple[SaleEvent]]:
        if status is SaleEventStatus.BEFORE_EVENT:
            return stmt.where(SaleEvent.start_date > at)
        if status is SaleEventStatus.AFTER_EVENT:
            return stmt.where(SaleEvent.end_date < at)
        if status is SaleEventStatus.DURING_EVENT:
            return stmt.where(SaleEvent.start_date <= at, SaleEvent.end_date >= at)
        raise ValueError(f"Unsupported sale-event status: {status!r}")
