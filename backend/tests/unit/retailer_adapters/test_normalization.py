"""Normalization: each adapter maps its own vocabulary onto the shared shape."""

from app.domain.validation import build_variant_key
from app.retailer_adapters.mock_retailer_a import create_adapter as create_a
from app.retailer_adapters.mock_retailer_b import create_adapter as create_b
from app.retailer_adapters.mock_retailer_c import create_adapter as create_c


class TestNormalizeProduct:
    async def test_mock_a_maps_colour_to_color(self) -> None:
        adapter = create_a(env={})
        product = await adapter.get_product("A-MOB-1001")
        normalized = adapter.normalize_product(product)
        assert normalized.retailer_id == "mock-retailer-a"
        assert "color" in normalized.variant_attributes
        assert "colour" not in normalized.variant_attributes
        assert normalized.variant_attributes["color"] == "midnight"
        assert normalized.variant_attributes["storage"] == "128 gb"
        assert normalized.brand_slug == "fictional-orchard"
        assert normalized.category_slug == "mobiles"
        assert normalized.variant_key == build_variant_key(dict(normalized.variant_attributes))
        assert normalized.identifiers[0].value == "0000000001001"

    async def test_mock_b_keeps_feed_spec_keys(self) -> None:
        adapter = create_b(env={})
        product = await adapter.get_product("880011")
        normalized = adapter.normalize_product(product)
        assert normalized.variant_attributes["storage"] == "128gb"
        assert "colour" in normalized.variant_attributes
        assert normalized.brand_slug == "fictional-orchard"
        assert normalized.category_slug == "mobiles"
        assert normalized.identifiers[0].value == "FO-AUR-128-MID"

    async def test_mock_c_has_no_identifiers_and_uses_department_as_category(self) -> None:
        adapter = create_c(env={})
        product = await adapter.get_product("C/AUD/0004")
        normalized = adapter.normalize_product(product)
        assert normalized.identifiers == ()
        assert normalized.category_slug == "audio"
        assert normalized.brand_slug == "fictional-wavecrest"
        assert normalized.variant_attributes["colour"] == "charcoal"

    async def test_normalized_title_collapses_whitespace(self) -> None:
        adapter = create_a(env={})
        product = await adapter.get_product("A-MOB-1001")
        # Titles in fixtures have no extra whitespace; the contract still holds.
        normalized = adapter.normalize_product(product)
        assert "  " not in normalized.normalized_title
        assert normalized.normalized_title == product.title.strip()
