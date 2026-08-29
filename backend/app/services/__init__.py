"""Thin service-layer boundaries, introduced only where they are genuinely required.

Most catalogue API routes call a single repository directly and need no additional layer. A
service exists here only when a route's job genuinely spans more than one repository/decision
(`price_service.py`), orchestrates adapters plus persistence (`product_discovery_service.py`),
or projects persisted listings into the price comparison engine (`price_comparison_service.py`),
or projects stored snapshots into historical intelligence (`price_history_service.py`), or
projects sale events and stored snapshots into sale-event intelligence
(`sale_event_service.py`).
Business logic that predicts prices, matches products semantically, or recommends
BUY_NOW/WAIT/WATCH does not belong here.
"""
