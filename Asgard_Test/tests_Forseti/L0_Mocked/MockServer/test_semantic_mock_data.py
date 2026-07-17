"""
L0 Unit Tests for semantically correlated mock data generation.

Covers plan 06-B item 3: Luhn-valid card numbers and coherent
locale rows (city/region/postcode/country/currency drawn together),
plus example-first generation already present in the service.
"""

import random

import pytest

from Asgard.Forseti.MockServer.models.mock_models import MockDataConfig
from Asgard.Forseti.MockServer.services._mock_data_generator_helpers import (
    LOCALE_ROWS,
    generate_correlated_address,
    generate_country_code,
    generate_currency_code,
    generate_luhn_card,
    infer_from_property_name,
    is_luhn_valid,
    luhn_checksum_digit,
    pick_locale_row,
)
from Asgard.Forseti.MockServer.services.mock_data_generator import (
    MockDataGeneratorService,
)


class TestLuhnGeneration:
    def test_generated_cards_are_luhn_valid(self):
        rng = random.Random(1234)
        for _ in range(1000):
            card = generate_luhn_card(rng)
            assert is_luhn_valid(card), card

    def test_seeded_generation_is_reproducible(self):
        rng1 = random.Random(42)
        rng2 = random.Random(42)
        cards1 = [generate_luhn_card(rng1) for _ in range(10)]
        cards2 = [generate_luhn_card(rng2) for _ in range(10)]
        assert cards1 == cards2

    def test_checksum_digit_makes_number_valid(self):
        partial = "411111111111111"
        digit = luhn_checksum_digit(partial)
        assert is_luhn_valid(partial + digit)

    def test_invalid_number_detected(self):
        assert is_luhn_valid("4111111111111112") is False

    def test_different_schemes_produce_different_prefixes(self):
        rng = random.Random(5)
        visa = generate_luhn_card(rng, scheme="visa")
        rng2 = random.Random(5)
        amex = generate_luhn_card(rng2, scheme="amex")
        assert visa.startswith("4")
        assert amex.startswith("34")


class TestLocaleCoherence:
    def test_locale_row_fields_are_internally_consistent(self):
        for row in LOCALE_ROWS:
            assert row["country"] and row["city"] and row["currency"] and row["country_code"]

    def test_correlated_address_uses_single_row(self):
        rng = random.Random(7)
        addr = generate_correlated_address(rng)
        matching = [
            r for r in LOCALE_ROWS
            if r["city"] == addr["city"] and r["country"] == addr["country"]
            and r["postcode"] == addr["postcode"]
        ]
        assert len(matching) == 1

    def test_currency_and_country_code_come_from_a_locale_row(self):
        rng = random.Random(9)
        currency = generate_currency_code(rng)
        rng2 = random.Random(9)
        country_code = generate_country_code(rng2)
        row = pick_locale_row(random.Random(9))
        assert currency == row["currency"]
        assert country_code == row["country_code"]

    def test_pick_locale_row_returns_known_row(self):
        rng = random.Random(3)
        row = pick_locale_row(rng)
        assert row in LOCALE_ROWS


class TestInferFromPropertyNameSemantics:
    def test_card_number_property_generates_luhn_valid_value(self):
        rng = random.Random(11)
        value = infer_from_property_name("card_number", rng)
        assert value is not None
        assert is_luhn_valid(value)

    def test_currency_property_returns_iso4217_style_code(self):
        rng = random.Random(11)
        value = infer_from_property_name("currency", rng)
        assert value in {row["currency"] for row in LOCALE_ROWS}

    def test_country_code_property_returns_alpha2(self):
        rng = random.Random(11)
        value = infer_from_property_name("country_code", rng)
        assert value in {row["country_code"] for row in LOCALE_ROWS}
        assert len(value) == 2

    def test_postcode_property_returns_coherent_row_value(self):
        rng = random.Random(11)
        value = infer_from_property_name("postal_code", rng)
        assert value in {row["postcode"] for row in LOCALE_ROWS}


class TestExampleFirstGeneration:
    """Service already prefers `example`/`examples` over synthesis; guard the contract."""

    def test_example_takes_precedence_over_synthesis(self):
        service = MockDataGeneratorService(MockDataConfig(use_examples=True))
        schema = {"type": "string", "example": "curated-value"}
        result = service.generate_from_schema(schema)
        assert result.data == "curated-value"
        assert result.generation_strategy == "example"

    def test_synthetic_flag_can_force_generation(self):
        service = MockDataGeneratorService(MockDataConfig(use_examples=False))
        schema = {"type": "string", "example": "curated-value"}
        result = service.generate_from_schema(schema)
        assert result.generation_strategy != "example"
