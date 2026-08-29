"""Thin service-layer boundaries, introduced only where they are genuinely required.

Most catalogue API routes call a single repository directly and need no additional layer. A
service exists here only when a route's job genuinely spans more than one repository/decision
(`price_service.py`), orchestrates adapters plus persistence (`product_discovery_service.py`),
or projects persisted listings into the price comparison engine (`price_comparison_service.py`),
or projects stored snapshots into historical intelligence (`price_history_service.py`), or
projects sale events and stored snapshots into sale-event intelligence
(`sale_event_service.py`), or projects those records into sale-price inference
(`sale_price_prediction_service.py`), or composes history, sale events, and Phase 10
predictions into the Phase 11 recommendation engine (`recommendation_service.py`).
Business logic that matches products semantically does not belong here.
"""
