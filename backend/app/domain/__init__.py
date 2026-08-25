"""Framework-independent domain layer: entities' invariants, enums, and value rules.

This package must never import from `app.db`, `app.api`, or any retailer adapter. It exists so
that the core business rules (what makes a slug valid, what a price observation's availability
states are, how a product variant's identity key is derived, ...) can be understood and tested
without a database or a web framework in the loop.
"""
