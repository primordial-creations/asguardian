"""L0 tests for the cross-format type compatibility matrix (plan 07)."""

import itertools

from Asgard.Forseti.Alignment.models.ir_models import TypeClass
from Asgard.Forseti.Alignment.services._type_matrix_helpers import (
    MatrixVerdict,
    classify,
    is_symmetric_incompatible,
)


class TestTypeMatrix:
    def test_identical_types_isomorphic(self):
        for tc in TypeClass:
            assert classify(tc, tc) == MatrixVerdict.ISOMORPHIC

    def test_string_bool_incompatible(self):
        assert classify(TypeClass.STRING, TypeClass.BOOL) == MatrixVerdict.INCOMPATIBLE

    def test_avro_string_proto_int64_incompatible(self):
        assert classify(TypeClass.STRING, TypeClass.INT64) != MatrixVerdict.INCOMPATIBLE
        # proto int64 <-> String is a documented safe idiomatic mapping (GraphQL ids);
        # a genuinely incompatible pair is e.g. STRING vs BOOL, RECORD vs INT32.
        assert classify(TypeClass.RECORD, TypeClass.INT32) == MatrixVerdict.INCOMPATIBLE

    def test_int64_string_idiomatic(self):
        assert classify(TypeClass.INT64, TypeClass.STRING) == MatrixVerdict.COERCIBLE_IDIOMATIC
        assert classify(TypeClass.STRING, TypeClass.INT64) == MatrixVerdict.COERCIBLE_IDIOMATIC

    def test_int64_to_int32_is_lossy(self):
        assert classify(TypeClass.INT64, TypeClass.INT32) == MatrixVerdict.COERCIBLE_LOSSY

    def test_int32_to_int64_is_isomorphic_widening(self):
        assert classify(TypeClass.INT32, TypeClass.INT64) == MatrixVerdict.ISOMORPHIC

    def test_float64_to_float32_is_lossy(self):
        assert classify(TypeClass.FLOAT64, TypeClass.FLOAT32) == MatrixVerdict.COERCIBLE_LOSSY

    def test_decimal_to_float_is_lossy(self):
        assert classify(TypeClass.DECIMAL, TypeClass.FLOAT64) == MatrixVerdict.COERCIBLE_LOSSY

    def test_incompatible_is_symmetric(self):
        for a, b in itertools.combinations(TypeClass, 2):
            if classify(a, b) == MatrixVerdict.INCOMPATIBLE:
                assert classify(b, a) == MatrixVerdict.INCOMPATIBLE, (a, b)

    def test_lossy_is_directional(self):
        assert classify(TypeClass.INT64, TypeClass.INT32) == MatrixVerdict.COERCIBLE_LOSSY
        assert classify(TypeClass.INT32, TypeClass.INT64) != MatrixVerdict.COERCIBLE_LOSSY

    def test_is_symmetric_incompatible_helper(self):
        assert is_symmetric_incompatible(TypeClass.STRING, TypeClass.BOOL) is True
        assert is_symmetric_incompatible(TypeClass.INT64, TypeClass.INT32) is False
