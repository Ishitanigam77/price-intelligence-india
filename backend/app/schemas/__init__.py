"""Pydantic API schemas (request/response DTOs).

These are the API layer's own contract types — deliberately kept separate from the SQLAlchemy
ORM models in `app.db.models` so that internal persistence details (column types, relationship
loading, mixins) never leak directly into the HTTP contract, and so the API contract can evolve
independently of the database schema.

No business logic lives here: these are data-shape and validation-only definitions.
"""
