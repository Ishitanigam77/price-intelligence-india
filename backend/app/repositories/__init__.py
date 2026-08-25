"""Data access layer: repositories expose domain-oriented operations over SQLAlchemy models.

Callers (future API routers, services, collectors) depend on these repositories rather than
issuing SQLAlchemy queries directly, keeping ORM/query details out of the domain and API
layers.
"""
