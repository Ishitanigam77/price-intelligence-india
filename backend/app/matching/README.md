# app/matching/

Product matching engine: resolves normalized listings to existing Product Variants using, in
order of preference, GTIN/EAN/UPC, manufacturer part/model number, brand + variant attributes,
normalized text similarity, and semantic embeddings (Sentence Transformers). Never merges
distinct variants.

**Status**: empty scaffold. Introduced in **Phase 3 — Product Normalization & Matching**
(deterministic matching first; semantic matching groundwork follows).
