"""Thin service-layer boundaries, introduced only where they are genuinely required.

Most Phase 2 API routes call a single repository directly and need no additional layer. A
service exists here only when a route's job genuinely spans more than one repository/decision
(see `price_service.py`). Business logic that computes/predicts/compares prices does not belong
here — see `ROADMAP.md` Phase 4 onward.
"""
