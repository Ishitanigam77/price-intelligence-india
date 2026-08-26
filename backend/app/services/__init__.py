"""Thin service-layer boundaries, introduced only where they are genuinely required.

Most catalogue API routes call a single repository directly and need no additional layer. A
service exists here only when a route's job genuinely spans more than one repository/decision
(`price_service.py`) or orchestrates adapters plus persistence (`product_discovery_service.py`).
Business logic that computes/predicts/compares prices, matches products semantically, or
recommends BUY_NOW/WAIT/WATCH does not belong here.
"""
