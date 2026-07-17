"""L0 tests for lexical tokenization (plan 07 testing notes)."""

from Asgard.Forseti.Alignment.services._lexical_helpers import tokenize


class TestTokenize:
    def test_camel_case(self):
        assert tokenize("orderId") == ("order", "id")

    def test_snake_case(self):
        assert tokenize("order_id") == ("order", "id")

    def test_upper_snake_case(self):
        assert tokenize("ORDER_ID") == ("order", "id")

    def test_pascal_case(self):
        assert tokenize("OrderID") == ("order", "id")

    def test_all_variants_equal(self):
        variants = ["orderId", "order_id", "ORDER_ID", "OrderID", "Order-Id"]
        tokens = {tokenize(v) for v in variants}
        assert tokens == {("order", "id")}

    def test_different_words_do_not_match(self):
        assert tokenize("orderId") != tokenize("orderedId")

    def test_empty_string(self):
        assert tokenize("") == ()

    def test_single_word(self):
        assert tokenize("name") == ("name",)
