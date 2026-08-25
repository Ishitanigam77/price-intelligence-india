"""Retailer adapters: the common framework (`base/`) plus one package per retailer.

Import the framework from `app.retailer_adapters.base`. This module intentionally imports no
adapter package, so importing the framework never drags a retailer integration (or a mock) into
the process — adapters are brought in explicitly, or through
`app.retailer_adapters.base.discovery`.
"""
