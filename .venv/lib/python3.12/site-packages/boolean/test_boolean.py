"""
Boolean Algebra.

Tests

Copyright (c) Sebastian Kraemer, basti.kr@gmail.com and others
SPDX-License-Identifier: BSD-2-Clause
"""

import unittest
from unittest.case import expectedFailure

from boolean import (
    TOKEN_AND,
    TOKEN_FALSE,
    TOKEN_LPAR,
    TOKEN_NOT,
    TOKEN_OR,
    TOKEN_RPAR,
    TOKEN_SYMBOL,
    TOKEN_TRUE,
    BooleanAlgebra,
    ParseError,
    Symbol,
)
from boolean.boolean import (
    PARSE_INVALID_EXPRESSION,
    PARSE_INVALID_NESTING,
    PARSE_INVALID_OPERATOR_SEQUENCE,
    PARSE_INVALID_SYMBOL_SEQUENCE,
    PARSE_UNKNOWN_TOKEN,
)


class BooleanAlgebraTestCase(unittest.TestCase):
    def test_creation(self):
        algebra = BooleanAlgebra()
        expr_str = "(a|b|c)&d&(~e|(f&g))"
        expr = algebra.parse(expr_str)
        assert str(expr) == expr_str

    def test_parse_with_mixed_operators_multilines_and_custom_symbol(self):
        class MySymbol(Symbol):
            pass

        expr_str = """(a or ~ b +_c  ) and
                      d & ( ! e_
                      | (my * g OR 1 or 0) ) AND that """

        algebra = BooleanAlgebra(Symbol_class=MySymbol)
        expr = algebra.parse(expr_str)

        expected = algebra.AND(
            algebra.OR(
                algebra.Symbol("a"),
                algebra.NOT(algebra.Symbol("b")),
                algebra.Symbol("_c"),
            ),
            algebra.Symbol("d"),
            algebra.OR(
                algebra.NOT(algebra.Symbol("e_")),
                algebra.OR(
                    algebra.AND(
                        algebra.Symbol("my"),
                        algebra.Symbol("g"),
                    ),
                    algebra.TRUE,
                    algebra.FALSE,
                ),
            ),
            algebra.Symbol("that"),
        )

        assert expr.pretty() == expected.pretty()
        assert expr == expected

    def test_parse_recognizes_trueish_and_falsish_symbol_tokens(self):
        expr_str = "True or False or None or 0 or 1 or TRue or FalSE or NONe"
        algebra = BooleanAlgebra()
        expr = algebra.parse(expr_str)
        expected = algebra.OR(
            algebra.TRUE,
            algebra.FALSE,
            algebra.FALSE,
            algebra.FALSE,
            algebra.TRUE,
            algebra.TRUE,
            algebra.FALSE,
            algebra.FALSE,
        )
        assert expr == expected

    def test_parse_can_use_iterable_from_alternative_tokenizer(self):
        class CustomSymbol(Symbol):
            pass

        class CustomAlgebra(BooleanAlgebra):
            def __init__(self, Symbol_class=CustomSymbol):
                super(CustomAlgebra, self).__init__(Symbol_class=Symbol_class)

            def tokenize(self, s):
                "Sample tokenizer using custom operators and symbols"
                ops = {
                    "WHY_NOT": TOKEN_OR,
                    "ALSO": TOKEN_AND,
                    "NEITHER": TOKEN_NOT,
                    "(": TOKEN_LPAR,
                    ")": TOKEN_RPAR,
                }

                for row, line in enumerate(s.splitlines(False)):
                    for col, tok in enumerate(line.split()):
                        if tok in ops:
                            yield ops[tok], tok, (row, col)
                        elif tok == "Custom":
                            yield self.Symbol(tok), tok, (row, col)
                        else:
                            yield TOKEN_SYMBOL, tok, (row, col)

        expr_str = """( Custom WHY_NOT regular ) ALSO NEITHER  (
                      not_custom ALSO standard )
                   """

        algebra = CustomAlgebra()
        expr = algebra.parse(expr_str)
        expected = algebra.AND(
            algebra.OR(
                algebra.Symbol("Custom"),
                algebra.Symbol("regular"),
            ),
            algebra.NOT(
                algebra.AND(
                    algebra.Symbol("not_custom"),
                    algebra.Symbol("standard"),
                ),
            ),
        )
        assert expr == expected

    def test_parse_with_advanced_tokenizer_example(self):
        import tokenize
        from io import StringIO

        class PlainVar(Symbol):
            "Plain boolean variable"

        class ColonDotVar(Symbol):
            "Colon and dot-separated string boolean variable"

        class AdvancedAlgebra(BooleanAlgebra):
            def tokenize(self, expr):
                """
                Example custom tokenizer derived from the standard Python tokenizer
                with a few extra features: #-style comments are supported and a
                colon- and dot-separated string is recognized and stored in custom
                symbols. In contrast with the standard tokenizer, only these
                boolean operators are recognized : & | ! and or not.

                For more advanced tokenization you could also consider forking the
                `tokenize` standard library module.
                """

                if not isinstance(expr, str):
                    raise TypeError("expr must be string but it is %s." % type(expr))

                # mapping of lowercase token strings to a token object instance for
                # standard operators, parens and common true or false symbols
                TOKENS = {
                    "&": TOKEN_AND,
                    "and": TOKEN_AND,
                    "|": TOKEN_OR,
                    "or": TOKEN_OR,
                    "!": TOKEN_NOT,
                    "not": TOKEN_NOT,
                    "(": TOKEN_LPAR,
                    ")": TOKEN_RPAR,
                    "true": TOKEN_TRUE,
                    "1": TOKEN_TRUE,
                    "false": TOKEN_FALSE,
                    "0": TOKEN_FALSE,
                    "none": TOKEN_FALSE,
                }

                ignored_token_types = (
                    tokenize.NL,
                    tokenize.NEWLINE,
                    tokenize.COMMENT,
                    tokenize.INDENT,
                    tokenize.DEDENT,
                    tokenize.ENDMARKER,
                )

                # note: an unbalanced expression may raise a TokenError here.
                tokens = (
                    (
                        toktype,
                        tok,
                        row,
                        col,
                    )
                    for toktype, tok, (
                        row,
                        col,
                    ), _, _ in tokenize.generate_tokens(StringIO(expr).readline)
                    if tok and tok.strip()
                )

                COLON_DOT = (
                    ":",
                    ".",
                )

                def build_symbol(current_dotted):
                    if current_dotted:
                        if any(s in current_dotted for s in COLON_DOT):
                            sym = ColonDotVar(current_dotted)
                        else:
                            sym = PlainVar(current_dotted)
                        return sym

                # accumulator for dotted symbols that span several `tokenize` tokens
                dotted, srow, scol = "", None, None

                for toktype, tok, row, col in tokens:
                    if toktype in ignored_token_types:
                        # we reached a break point and should yield the current dotted
                        symbol = build_symbol(dotted)
                        if symbol is not None:
                            yield symbol, dotted, (srow, scol)
                            dotted, srow, scol = "", None, None

                        continue

                    std_token = TOKENS.get(tok.lower())
                    if std_token is not None:
                        # we reached a break point and should yield the current dotted
                        symbol = build_symbol(dotted)
                        if symbol is not None:
                            yield symbol, dotted, (srow, scol)
                            dotted, srow, scol = "", 0, 0

                        yield std_token, tok, (row, col)

                        continue

                    if toktype == tokenize.NAME or (toktype == tokenize.OP and tok in COLON_DOT):
                        if not dotted:
                            srow = row
                            scol = col
                        dotted += tok

                    else:
                        raise TypeError(
                            "Unknown token: %(tok)r at line: %(row)r, column: %(col)r" % locals()
                        )

        test_expr = """
            (colon1:dot1.dot2 or colon2_name:col_on3:do_t1.do_t2.do_t3 )
            and
            ( plain_symbol & !Custom )
        """

        algebra = AdvancedAlgebra()
        expr = algebra.parse(test_expr)
        expected = algebra.AND(
            algebra.OR(
                ColonDotVar("colon1:dot1.dot2"),
                ColonDotVar("colon2_name:col_on3:do_t1.do_t2.do_t3"),
            ),
            algebra.AND(PlainVar("plain_symbol"), algebra.NOT(PlainVar("Custom"))),
        )
        assert expr == expected

    def test_allowing_additional_characters_in_tokens(self):
        algebra = BooleanAlgebra(allowed_in_token=(".", "_", "-", "+"))
        test_expr = "l-a AND b+c"

        expr = algebra.parse(test_expr)
        expected = algebra.AND(algebra.Symbol("l-a"), algebra.Symbol("b+c"))
        assert expr == expected

    def test_parse_raise_ParseError1(self):
        algebra = BooleanAlgebra()
        expr = "l-a AND none"

        try:
            algebra.parse(expr)
            self.fail("Exception should be raised when parsing '%s'" % expr)
        except ParseError as pe:
            assert pe.error_code == PARSE_UNKNOWN_TOKEN

    def test_parse_raise_ParseError2(self):
        algebra = BooleanAlgebra()
        expr = "(l-a + AND l-b"
        try:
            algebra.parse(expr)
            self.fail("Exception should be raised when parsing '%s'" % expr)
        except ParseError as pe:
            assert pe.error_code == PARSE_UNKNOWN_TOKEN

    def test_parse_raise_ParseError3(self):
        algebra = BooleanAlgebra()
        expr = "(l-a + AND l-b)"
        try:
            algebra.parse(expr)
            self.fail("Exception should be raised when parsing '%s'" % expr)
        except ParseError as pe:
            assert pe.error_code == PARSE_UNKNOWN_TOKEN

    def test_parse_raise_ParseError4(self):
        algebra = BooleanAlgebra()
        expr = "(l-a AND l-b"
        try:
            algebra.parse(expr)
            self.fail("Exception should be raised when parsing '%s'" % expr)
        except ParseError as pe:
            assert pe.error_code == PARSE_UNKNOWN_TOKEN

    def test_parse_raise_ParseError5(self):
        algebra = BooleanAlgebra()
        expr = "(l-a + AND l-b))"
        try:
            algebra.parse(expr)
            self.fail("Exception should be raised when parsing '%s'" % expr)
        except ParseError as pe:
            assert pe.error_code == PARSE_UNKNOWN_TOKEN

    def test_parse_raise_ParseError6(self):
        algebra = BooleanAlgebra()
        expr = "(l-a  AND l-b))"
        try:
            algebra.parse(expr)
            self.fail("Exception should be raised when parsing '%s'" % expr)
        except ParseError as pe:
            assert pe.error_code == PARSE_UNKNOWN_TOKEN

    def test_parse_raise_ParseError7(self):
        algebra = BooleanAlgebra()
        expr = "l-a AND"
        try:
            algebra.parse(expr)
            self.fail("Exception should be raised when parsing '%s'" % expr)
        except ParseError as pe:
            assert pe.error_code == PARSE_UNKNOWN_TOKEN

    def test_parse_raise_ParseError8(self):
        algebra = BooleanAlgebra()
        expr = "OR l-a"
        try:
            algebra.parse(expr)
            self.fail("Exception should be raised when parsing '%s'" % expr)
        except ParseError as pe:
            assert pe.error_code == PARSE_INVALID_OPERATOR_SEQUENCE

    def test_parse_raise_ParseError9(self):
        algebra = BooleanAlgebra()
        expr = "+ l-a"
        try:
            algebra.parse(expr)
            self.fail("Exception should be raised when parsing '%s'" % expr)
        except ParseError as pe:
            assert pe.error_code == PARSE_INVALID_OPERATOR_SEQUENCE

    def test_parse_side_by_side_symbols_should_raise_exception_but_not(self):
        algebra = BooleanAlgebra()
        expr_str = "a or b c"
        try:
            algebra.parse(expr_str)
        except ParseError as pe:
            assert pe.error_code == PARSE_INVALID_SYMBOL_SEQUENCE

    def test_parse_side_by_side_symbols_should_raise_exception_but_not2(self):
        algebra = BooleanAlgebra()
        expr_str = "(a or b) c"
        try:
            algebra.parse(expr_str)
        except ParseError as pe:
            assert pe.error_code == PARSE_INVALID_EXPRESSION

    def test_parse_side_by_side_symbols_raise_exception(self):
        algebra = BooleanAlgebra()
        expr_str = "a b"
        try:
            algebra.parse(expr_str)
        except ParseError as pe:
            assert pe.error_code == PARSE_INVALID_SYMBOL_SEQUENCE

    def test_parse_side_by_side_symbols_with_parens_raise_exception(self):
        algebra = BooleanAlgebra()
        expr_str = "(a) (b)"
        try:
            algebra.parse(expr_str)
        except ParseError as pe:
            assert pe.error_code == PARSE_INVALID_NESTING


class BaseElementTestCase(unittest.TestCase):
    def test_creation(self):
        from boolean.boolean import BaseElement

        algebra = BooleanAlgebra()
        assert algebra.TRUE == algebra.TRUE
        BaseElement()
        self.assertRaises(TypeError, BaseElement, 2)
        self.assertRaises(TypeError, BaseElement, "a")
        assert algebra.TRUE is algebra.TRUE
        assert algebra.TRUE is not algebra.FALSE
        assert algebra.FALSE is algebra.FALSE
        assert bool(algebra.TRUE) is True
        assert bool(algebra.FALSE) is False
        assert algebra.TRUE == True
        assert algebra.FALSE == False

    def test_literals(self):
        algebra = BooleanAlgebra()
        assert algebra.TRUE.literals == set()
        assert algebra.FALSE.literals == set()

    def test_literalize(self):
        algebra = BooleanAlgebra()
        assert algebra.TRUE.literalize() == algebra.TRUE
        assert algebra.FALSE.literalize() == algebra.FALSE

    def test_simplify(self):
        algebra = BooleanAlgebra()
        assert algebra.TRUE.simplify() == algebra.TRUE
        assert algebra.FALSE.simplify() == algebra.FALSE

    def test_simplify_two_algebra(self):
        algebra1 = BooleanAlgebra()
        algebra2 = BooleanAlgebra()
        assert algebra1.TRUE.simplify() == algebra2.TRUE
        assert algebra1.FALSE.simplify() == algebra2.FALSE

    def test_dual(self):
        algebra = BooleanAlgebra()
        assert algebra.TRUE.dual == algebra.FALSE
        assert algebra.FALSE.dual == algebra.TRUE

    def test_equality(self):
        algebra = BooleanAlgebra()
        assert algebra.TRUE == algebra.TRUE
        assert algebra.FALSE == algebra.FALSE
        assert algebra.TRUE != algebra.FALSE

    def test_order(self):
        algebra = BooleanAlgebra()
        assert algebra.FALSE < algebra.TRUE
        assert algebra.TRUE > algebra.FALSE

    def test_printing(self):
        algebra = BooleanAlgebra()
        assert str(algebra.TRUE) == "1"
        assert str(algebra.FALSE) == "0"
        assert repr(algebra.TRUE) == "TRUE"
        assert repr(algebra.FALSE) == "FALSE"


class SymbolTestCase(unittest.TestCase):
    def test_init(self):
        Symbol(1)
        Symbol("a")
        Symbol(None)
        Symbol(sum)
        Symbol((1, 2, 3))
        Symbol([1, 2])

    def test_isliteral(self):
        assert Symbol(1).isliteral is True

    def test_literals(self):
        l1 = Symbol(1)
        l2 = Symbol(1)
        assert l1 in l1.literals
        assert l1 in l2.literals
        assert l2 in l1.literals
        assert l2 in l2.literals
        self.assertRaises(AttributeError, setattr, l1, "literals", 1)

    def test_literalize(self):
        s = Symbol(1)
        assert s.literalize() == s

    def test_simplify(self):
        s = Symbol(1)
        assert s.simplify() == s

    def test_simplify_different_instances(self):
        s1 = Symbol(1)
        s2 = Symbol(1)
        assert s1.simplify() == s2.simplify()

    def test_equal_symbols(self):
        algebra = BooleanAlgebra()
        a = algebra.Symbol("a")
        a2 = algebra.Symbol("a")

        c = algebra.Symbol("b")
        d = algebra.Symbol("d")
        e = algebra.Symbol("e")

        # Test __eq__.
        assert a == a
        assert a == a2
        assert not a == c
        assert not a2 == c
        assert d == d
        assert not d == e
        assert not a == d
        # Test __ne__.
        assert not a != a
        assert not a != a2
        assert a != c
        assert a2 != c

    def test_order(self):
        S = Symbol
        assert S("x") < S("y")
        assert S("y") > S("x")
        assert S(1) < S(2)
        assert S(2) > S(1)

    def test_printing(self):
        assert str(Symbol("a")) == "a"
        assert str(Symbol(1)) == "1"
        assert repr(Symbol("a")) == "Symbol('a')"
        assert repr(Symbol(1)) == "Symbol(1)"


class NOTTestCase(unittest.TestCase):
    def test_init(self):
        algebra = BooleanAlgebra()
        self.assertRaises(TypeError, algebra.NOT)
        self.assertRaises(TypeError, algebra.NOT, "a", "b")
        algebra.NOT(algebra.Symbol("a"))
        assert (algebra.NOT(algebra.TRUE)).simplify() == algebra.FALSE
        assert (algebra.NOT(algebra.FALSE)).simplify() == algebra.TRUE

    def test_isliteral(self):
        algebra = BooleanAlgebra()
        s = algebra.Symbol(1)
        assert algebra.NOT(s).isliteral
        assert not algebra.parse("~(a|b)").isliteral

    def test_literals(self):
        algebra = BooleanAlgebra()
        a = algebra.Symbol("a")
        l = ~a
        assert l.isliteral
        assert l in l.literals
        assert len(l.literals) == 1

        l = algebra.parse("~(a&a)")
        assert not l.isliteral
        assert a in l.literals
        assert len(l.literals) == 1

        l = algebra.parse("~(a&a)", simplify=True)
        assert l.isliteral

    def test_literalize(self):
        parse = BooleanAlgebra().parse
        assert parse("~a") == parse("~a").literalize()
        assert parse("~a|~b") == parse("~(a&b)").literalize()
        assert parse("~a&~b") == parse("~(a|b)").literalize()

    def test_simplify(self):
        algebra = BooleanAlgebra()
        a = algebra.Symbol("a")
        assert ~a == ~a
        assert algebra.Symbol("a") == algebra.Symbol("a")
        assert algebra.parse("~~a") != a
        assert (~~a).simplify() == a
        assert (~~~a).simplify() == ~a
        assert (~~~~a).simplify() == a
        assert (~(a & a & a)).simplify() == (~(a & a & a)).simplify()
        assert algebra.parse("~~a", simplify=True) == a
        algebra2 = BooleanAlgebra()
        assert algebra2.parse("~~a", simplify=True) == a

    def test_cancel(self):
        algebra = BooleanAlgebra()
        a = algebra.Symbol("a")
        assert (~a).cancel() == ~a
        assert algebra.parse("~~a").cancel() == a
        assert algebra.parse("~~~a").cancel() == ~a
        assert algebra.parse("~~~~a").cancel() == a

    def test_demorgan(self):
        algebra = BooleanAlgebra()
        a = algebra.Symbol("a")
        b = algebra.Symbol("b")
        c = algebra.Symbol("c")
        assert algebra.parse("~(a&b)").demorgan() == ~a | ~b
        assert algebra.parse("~(a|b|c)").demorgan() == algebra.parse("~a&~b&~c")
        assert algebra.parse("~(~a&b)").demorgan() == a | ~b
        assert (~~(a & b | c)).demorgan() == a & b | c
        assert (~~~(a & b | c)).demorgan() == ~(a & b) & ~c
        assert algebra.parse("~" * 10 + "(a&b|c)").demorgan() == a & b | c
        assert algebra.parse("~" * 11 + "(a&b|c)").demorgan() == (~(a & b | c)).demorgan()
        _0 = algebra.FALSE
        _1 = algebra.TRUE
        assert (~(_0)).demorgan() == _1
        assert (~(_1)).demorgan() == _0

    def test_order(self):
        algebra = BooleanAlgebra()
        x = algebra.Symbol(1)
        y = algebra.Symbol(2)
        assert x < ~x
        assert ~x > x
        assert ~x < y
        assert y > ~x

    def test_printing(self):
        algebra = BooleanAlgebra()
        a = algebra.Symbol("a")
        assert str(~a) == "~a"
        assert repr(~a) == "NOT(Symbol('a'))"
        expr = algebra.parse("~(a&a)")
        assert str(expr) == "~(a&a)"
        assert repr(expr), "NOT(AND(Symbol('a') == Symbol('a')))"


class DualBaseTestCase(unittest.TestCase):

    maxDiff = None

    def test_init(self):
        from boolean.boolean import DualBase

        a, b, c = Symbol("a"), Symbol("b"), Symbol("c")
        t1 = DualBase(a, b)
        t2 = DualBase(a, b, c)
        t3 = DualBase(a, a)
        t4 = DualBase(a, b, c)

        self.assertRaises(TypeError, DualBase)
        for term in (t1, t2, t3, t4):
            assert isinstance(term, DualBase)

    def test_isliteral(self):
        from boolean.boolean import DualBase

        a, b, c = Symbol("a"), Symbol("b"), Symbol("c")
        t1 = DualBase(a, b)
        t2 = DualBase(a, b, c)

        assert not t1.isliteral
        assert not t2.isliteral

    def test_literals(self):
        from boolean.boolean import DualBase

        a, b, c = Symbol("a"), Symbol("b"), Symbol("c")
        t1 = DualBase(a, b)
        t2 = DualBase(a, b, c)
        t3 = DualBase(a, a)
        t4 = DualBase(a, b, c)

        for term in (t1, t2, t3, t4):
            assert a in term.literals
        for term in (t1, t2, t4):
            assert b in term.literals
        for term in (t2, t4):
            assert c in term.literals

    def test_literalize(self):
        parse = BooleanAlgebra().parse
        assert parse("a|~(b|c)").literalize() == parse("a|(~b&~c)")

    def test_annihilator(self):
        algebra = BooleanAlgebra()
        assert algebra.parse("a&a").annihilator == algebra.FALSE
        assert algebra.parse("a|a").annihilator == algebra.TRUE

    def test_identity(self):
        algebra = BooleanAlgebra()
        assert algebra.parse("a|b").identity == algebra.FALSE
        assert algebra.parse("a&b").identity == algebra.TRUE

    def test_dual(self):
        algebra = BooleanAlgebra()
        assert algebra.AND(algebra.Symbol("a"), algebra.Symbol("b")).dual == algebra.OR
        assert algebra.OR(algebra.Symbol("a"), algebra.Symbol("b")).dual == algebra.AND

        assert algebra.parse("a|b").dual == algebra.AND
        assert algebra.parse("a&b").dual == algebra.OR

    def test_simplify(self):
        algebra1 = BooleanAlgebra()
        algebra2 = BooleanAlgebra()
        a = algebra1.Symbol("a")
        b = algebra1.Symbol("b")
        c = algebra1.Symbol("c")

        _0 = algebra1.FALSE
        _1 = algebra1.TRUE
        # Idempotence
        assert (a & a).simplify() == a
        # Idempotence + Associativity
        assert (a | (a | b)).simplify() == a | b
        # Annihilation
        assert (a & _0).simplify() == _0
        assert (a | _1).simplify() == _1
        # Identity
        assert (a & _1).simplify() == a
        assert (a | _0).simplify() == a
        # Complementation
        assert (a & ~a).simplify() == _0
        assert (a | ~a).simplify() == _1
        # Absorption
        assert (a & (a | b)).simplify() == a
        assert (a | (a & b)).simplify() == a
        assert ((b & a) | (b & a & c)).simplify() == b & a

        # Elimination
        assert ((a & ~b) | (a & b)).simplify() == a

        # Commutativity + Non-Commutativity
        sorted_expression = (b & b & a).simplify()
        unsorted_expression = (b & b & a).simplify(sort=False)
        assert unsorted_expression == sorted_expression
        assert sorted_expression.pretty() != unsorted_expression.pretty()

        sorted_expression = (b | b | a).simplify()
        unsorted_expression = (b | b | a).simplify(sort=False)
        assert unsorted_expression == sorted_expression
        assert sorted_expression.pretty() != unsorted_expression.pretty()

        expected = algebra1.parse("(a&b)|(b&c)|(a&c)")
        result = algebra1.parse("(~a&b&c) | (a&~b&c) | (a&b&~c) | (a&b&c)", simplify=True)
        assert result == expected

        expected = algebra1.parse("(a&b)|(b&c)|(a&c)")
        result = algebra2.parse("(~a&b&c) | (a&~b&c) | (a&b&~c) | (a&b&c)", simplify=True)
        assert result == expected

        expected = algebra1.parse("b&d")
        result = algebra1.parse("(a&b&c&d) | (b&d)", simplify=True)
        assert result == expected

        expected = algebra1.parse("b&d")
        result = algebra2.parse("(a&b&c&d) | (b&d)", simplify=True)
        assert result == expected

        expected = algebra1.parse("(~b&~d&a) | (~c&~d&b) | (a&c&d)", simplify=True)
        result = algebra1.parse(
            """(~a&b&~c&~d) | (a&~b&~c&~d) | (a&~b&c&~d) |
                          (a&~b&c&d) | (a&b&~c&~d) | (a&b&c&d)""",
            simplify=True,
        )
        assert result.pretty() == expected.pretty()

        expected = algebra1.parse("(~b&~d&a) | (~c&~d&b) | (a&c&d)", simplify=True)
        result = algebra2.parse(
            """(~a&b&~c&~d) | (a&~b&~c&~d) | (a&~b&c&~d) |
                          (a&~b&c&d) | (a&b&~c&~d) | (a&b&c&d)""",
            simplify=True,
        )
        assert result.pretty() == expected.pretty()

    def test_absorption_invariant_to_order(self):
        algebra = BooleanAlgebra()

        a, b = algebra.symbols("a", "b")

        e = (~a | ~b) & b & ~a
        args = [
            ~a | ~b,
            ~a,
            b,
        ]

        result_original = e.absorb(args)

        args[1], args[2] = args[2], args[1]
        result_swapped = e.absorb(args)

        assert len(result_original) == 2
        assert len(result_swapped) == 2
        assert result_original[0] == result_swapped[1]
        assert result_original[1] == result_swapped[0]

    @expectedFailure
    def test_parse_complex_expression_should_create_same_expression_as_python(self):
        algebra = BooleanAlgebra()
        a, b, c = algebra.symbols(*"abc")

        test_expression_str = """(~a | ~b | ~c)"""
        parsed = algebra.parse(test_expression_str)
        test_expression = ~a | ~b | ~c  # & ~d
        # print()
        # print('parsed')
        # print(parsed.pretty())
        # print('python')
        # print(test_expression.pretty())
        # we have a different behavior for expressions built from python expressions
        # vs. expression built from an object tree vs. expression built from a parse
        assert parsed.pretty() == test_expression.pretty()
        assert parsed == test_expression

    @expectedFailure
    def test_simplify_complex_expression_parsed_with_simplify(self):
        # FIXME: THIS SHOULD NOT FAIL
        algebra = BooleanAlgebra()
        a = algebra.Symbol("a")
        b = algebra.Symbol("b")
        c = algebra.Symbol("c")
        d = algebra.Symbol("d")

        test_expression_str = """
            (~a&~b&~c&~d) | (~a&~b&~c&d) | (~a&b&~c&~d) |
            (~a&b&c&d) | (~a&b&~c&d) | (~a&b&c&~d) |
            (a&~b&~c&d) | (~a&b&c&d) | (a&~b&c&d) | (a&b&c&d)
            """

        parsed = algebra.parse(test_expression_str, simplify=True)

        test_expression = (
            (~a & ~b & ~c & ~d)
            | (~a & ~b & ~c & d)
            | (~a & b & ~c & ~d)
            | (~a & b & c & d)
            | (~a & b & ~c & d)
            | (~a & b & c & ~d)
            | (a & ~b & ~c & d)
            | (~a & b & c & d)
            | (a & ~b & c & d)
            | (a & b & c & d)
        ).simplify()

        # we have a different simplify behavior for expressions built from python expressions
        # vs. expression built from an object tree vs. expression built from a parse
        assert parsed.pretty() == test_expression.pretty()

    @expectedFailure
    def test_complex_expression_without_parens_parsed_or_built_in_python_should_be_identical(self):
        # FIXME: THIS SHOULD NOT FAIL
        algebra = BooleanAlgebra()
        a = algebra.Symbol("a")
        b = algebra.Symbol("b")
        c = algebra.Symbol("c")
        d = algebra.Symbol("d")

        test_expression_str = """
            ~a&~b&~c&~d | ~a&~b&~c&d | ~a&b&~c&~d |
            ~a&b&c&d | ~a&b&~c&d | ~a&b&c&~d |
            a&~b&~c&d | ~a&b&c&d | a&~b&c&d | a&b&c&d
            """

        parsed = algebra.parse(test_expression_str)

        test_expression = (
            ~a & ~b & ~c & ~d
            | ~a & ~b & ~c & d
            | ~a & b & ~c & ~d
            | ~a & b & c & d
            | ~a & b & ~c & d
            | ~a & b & c & ~d
            | a & ~b & ~c & d
            | ~a & b & c & d
            | a & ~b & c & d
            | a & b & c & d
        )

        assert parsed.pretty() == test_expression.pretty()

    @expectedFailure
    def test_simplify_complex_expression_parsed_then_simplified(self):
        # FIXME: THIS SHOULD NOT FAIL

        algebra = BooleanAlgebra()
        a = algebra.Symbol("a")
        b = algebra.Symbol("b")
        c = algebra.Symbol("c")
        d = algebra.Symbol("d")
        parse = algebra.parse

        test_expression_str = "".join(
            """
            (~a&~b&~c&~d) | (~a&~b&~c&d) | (~a&b&~c&~d) |
            (~a&b&c&d) | (~a&b&~c&d) | (~a&b&c&~d) |
            (a&~b&~c&d) | (~a&b&c&d) | (a&~b&c&d) | (a&b&c&d)
        """.split()
        )

        test_expression = (
            (~a & ~b & ~c & ~d)
            | (~a & ~b & ~c & d)
            | (~a & b & ~c & ~d)
            | (~a & b & c & d)
            | (~a & b & ~c & d)
            | (~a & b & c & ~d)
            | (a & ~b & ~c & d)
            | (~a & b & c & d)
            | (a & ~b & c & d)
            | (a & b & c & d)
        )

        parsed = parse(test_expression_str)
        assert test_expression_str == str(parsed)

        expected = (a & ~b & d) | (~a & b) | (~a & ~c) | (b & c & d)
        assert test_expression.simplify().pretty() == expected.pretty()

        parsed = parse(test_expression_str, simplify=True)

        # FIXME: THIS SHOULD NOT FAIL
        # we have a different simplify behavior for expressions built from python expressions
        # vs. expression built from an object tree vs. expression built from a parse
        assert parsed.simplify().pretty() == expected.simplify().pretty()

        expected_str = "(a&~b&d)|(~a&b)|(~a&~c)|(b&c&d)"
        assert str(parsed) == expected_str

        parsed2 = parse(test_expression_str)
        assert parsed2.simplify().pretty() == expected.pretty()

        assert str(parsed2.simplify()) == expected_str

        expected = algebra.OR(
            algebra.AND(
                algebra.NOT(algebra.Symbol("a")),
                algebra.NOT(algebra.Symbol("b")),
                algebra.NOT(algebra.Symbol("c")),
                algebra.NOT(algebra.Symbol("d")),
            ),
            algebra.AND(
                algebra.NOT(algebra.Symbol("a")),
                algebra.NOT(algebra.Symbol("b")),
                algebra.NOT(algebra.Symbol("c")),
                algebra.Symbol("d"),
            ),
            algebra.AND(
                algebra.NOT(algebra.Symbol("a")),
                algebra.Symbol("b"),
                algebra.NOT(algebra.Symbol("c")),
                algebra.NOT(algebra.Symbol("d")),
            ),
            algebra.AND(
                algebra.NOT(algebra.Symbol("a")),
                algebra.Symbol("b"),
                algebra.Symbol("c"),
                algebra.Symbol("d"),
            ),
            algebra.AND(
                algebra.NOT(algebra.Symbol("a")),
                algebra.Symbol("b"),
                algebra.NOT(algebra.Symbol("c")),
                algebra.Symbol("d"),
            ),
            algebra.AND(
                algebra.NOT(algebra.Symbol("a")),
                algebra.Symbol("b"),
                algebra.Symbol("c"),
                algebra.NOT(algebra.Symbol("d")),
            ),
            algebra.AND(
                algebra.Symbol("a"),
                algebra.NOT(algebra.Symbol("b")),
                algebra.NOT(algebra.Symbol("c")),
                algebra.Symbol("d"),
            ),
            algebra.AND(
                algebra.NOT(algebra.Symbol("a")),
                algebra.Symbol("b"),
                algebra.Symbol("c"),
                algebra.Symbol("d"),
            ),
            algebra.AND(
                algebra.Symbol("a"),
                algebra.NOT(algebra.Symbol("b")),
                algebra.Symbol("c"),
                algebra.Symbol("d"),
            ),
            algebra.AND(
                algebra.Symbol("a"), algebra.Symbol("b"), algebra.Symbol("c"), algebra.Symbol("d")
            ),
        )

        result = parse(test_expression_str)
        result = result.simplify()
        assert result == expected

    def test_parse_invalid_nested_and_should_raise_a_proper_exception(self):
        algebra = BooleanAlgebra()
        expr = """a (and b)"""

        with self.assertRaises(ParseError) as context:
            algebra.parse(expr)

            assert context.exception.error_code == PARSE_INVALID_NESTING

    def test_subtract(self):
        parse = BooleanAlgebra().parse
        expr = parse("a&b&c")
        p1 = parse("b&d")
        p2 = parse("a&c")
        result = parse("b")
        assert expr.subtract(p1, simplify=True) == expr
        assert expr.subtract(p2, simplify=True) == result

    def test_flatten(self):
        parse = BooleanAlgebra().parse

        t1 = parse("a & (b&c)")
        t2 = parse("a&b&c")
        assert t1 != t2
        assert t1.flatten() == t2

        t1 = parse("a | ((b&c) | (a&c)) | b")
        t2 = parse("a | (b&c) | (a&c) | b")
        assert t1 != t2
        assert t1.flatten() == t2

    def test_distributive(self):
        algebra = BooleanAlgebra()
        a = algebra.Symbol("a")
        b = algebra.Symbol("b")
        c = algebra.Symbol("c")
        d = algebra.Symbol("d")
        e = algebra.Symbol("e")
        assert (a & (b | c)).distributive() == (a & b) | (a & c)
        t1 = algebra.AND(a, (b | c), (d | e))
        t2 = algebra.OR(
            algebra.AND(a, b, d), algebra.AND(a, b, e), algebra.AND(a, c, d), algebra.AND(a, c, e)
        )
        assert t1.distributive() == t2

    def test_equal(self):
        from boolean.boolean import DualBase

        a, b, c = Symbol("a"), Symbol("b"), Symbol("c")
        t1 = DualBase(a, b)
        t1_2 = DualBase(b, a)

        t2 = DualBase(a, b, c)
        t2_2 = DualBase(b, c, a)

        # Test __eq__.
        assert t1 == t1
        assert t1_2 == t1
        assert t2_2 == t2
        assert not t1 == t2
        assert not t1 == 1
        assert not t1 is True
        assert not t1 is None

        # Test __ne__.
        assert not t1 != t1
        assert not t1_2 != t1
        assert not t2_2 != t2
        assert t1 != t2
        assert t1 != 1
        assert t1 is not True
        assert t1 is not None

    def test_order(self):
        algebra = BooleanAlgebra()
        x, y, z = algebra.Symbol(1), algebra.Symbol(2), algebra.Symbol(3)
        assert algebra.AND(x, y) < algebra.AND(x, y, z)
        assert not algebra.AND(x, y) > algebra.AND(x, y, z)
        assert algebra.AND(x, y) < algebra.AND(x, z)
        assert not algebra.AND(x, y) > algebra.AND(x, z)
        assert algebra.AND(x, y) < algebra.AND(y, z)
        assert not algebra.AND(x, y) > algebra.AND(y, z)
        assert not algebra.AND(x, y) < algebra.AND(x, y)
        assert not algebra.AND(x, y) > algebra.AND(x, y)

    def test_printing(self):
        parse = BooleanAlgebra().parse
        assert str(parse("a&a")) == "a&a"
        assert repr(parse("a&a")), "AND(Symbol('a') == Symbol('a'))"
        assert str(parse("a|a")) == "a|a"
        assert repr(parse("a|a")), "OR(Symbol('a') == Symbol('a'))"
        assert str(parse("(a|b)&c")) == "(a|b)&c"
        assert repr(parse("(a|b)&c")), "AND(OR(Symbol('a'), Symbol('b')) == Symbol('c'))"


class OtherTestCase(unittest.TestCase):
    def test_class_order(self):
        # FIXME: this test is cryptic: what does it do?
        algebra = BooleanAlgebra()
        order = (
            (algebra.TRUE, algebra.FALSE),
            (algebra.Symbol("y"), algebra.Symbol("x")),
            (algebra.parse("x&y"),),
            (algebra.parse("x|y"),),
        )
        for i, tests in enumerate(order):
            for case1 in tests:
                for j in range(i + 1, len(order)):
                    for case2 in order[j]:
                        assert case1 < case2
                        assert case2 > case1

    def test_parse(self):
        algebra = BooleanAlgebra()
        a, b, c = algebra.Symbol("a"), algebra.Symbol("b"), algebra.Symbol("c")
        assert algebra.parse("0") == algebra.FALSE
        assert algebra.parse("(0)") == algebra.FALSE
        assert algebra.parse("1") == algebra.TRUE
        assert algebra.parse("(1)") == algebra.TRUE
        assert algebra.parse("a") == a
        assert algebra.parse("(a)") == a
        assert algebra.parse("(a)") == a
        assert algebra.parse("~a") == algebra.parse("~(a)")
        assert algebra.parse("~(a)") == algebra.parse("(~a)")
        assert algebra.parse("~a") == ~a
        assert algebra.parse("(~a)") == ~a
        assert algebra.parse("~~a", simplify=True) == (~~a).simplify()
        assert algebra.parse("a&b") == a & b
        assert algebra.parse("~a&b") == ~a & b
        assert algebra.parse("a&~b") == a & ~b
        assert algebra.parse("a&b&c") == algebra.parse("a&b&c")
        assert algebra.parse("a&b&c") == algebra.AND(a, b, c)
        assert algebra.parse("~a&~b&~c") == algebra.parse("~a&~b&~c")
        assert algebra.parse("~a&~b&~c") == algebra.AND(~a, ~b, ~c)
        assert algebra.parse("a|b") == a | b
        assert algebra.parse("~a|b") == ~a | b
        assert algebra.parse("a|~b") == a | ~b
        assert algebra.parse("a|b|c") == algebra.parse("a|b|c")
        assert algebra.parse("a|b|c") == algebra.OR(a, b, c)
        assert algebra.parse("~a|~b|~c") == algebra.OR(~a, ~b, ~c)
        assert algebra.parse("(a|b)") == a | b
        assert algebra.parse("a&(a|b)", simplify=True) == (a & (a | b)).simplify()
        assert algebra.parse("a&(a|~b)", simplify=True) == (a & (a | ~b)).simplify()
        assert (
            algebra.parse("(a&b)|(b&((c|a)&(b|(c&a))))", simplify=True)
            == ((a & b) | (b & ((c | a) & (b | (c & a))))).simplify()
        )
        assert algebra.parse("(a&b)|(b&((c|a)&(b|(c&a))))", simplify=True) == algebra.parse(
            "a&b | b&(c|a)&(b|c&a)", simplify=True
        )
        assert algebra.Symbol("1abc") == algebra.parse("1abc")
        assert algebra.Symbol("_abc") == algebra.parse("_abc")

    def test_subs(self):
        algebra = BooleanAlgebra()
        a, b, c = algebra.Symbol("a"), algebra.Symbol("b"), algebra.Symbol("c")
        expr = a & b | c
        assert expr.subs({a: b}).simplify() == b | c
        assert expr.subs({a: a}).simplify() == expr
        assert expr.subs({a: b | c}).simplify() == algebra.parse("(b|c)&b|c").simplify()
        assert expr.subs({a & b: a}).simplify() == a | c
        assert expr.subs({c: algebra.TRUE}).simplify() == algebra.TRUE

    def test_subs_default(self):
        algebra = BooleanAlgebra()
        a, b, c = algebra.Symbol("a"), algebra.Symbol("b"), algebra.Symbol("c")
        expr = a & b | c
        assert expr.subs({}, default=algebra.TRUE).simplify() == algebra.TRUE
        assert (
            expr.subs({a: algebra.FALSE, c: algebra.FALSE}, default=algebra.TRUE).simplify()
            == algebra.FALSE
        )
        assert algebra.TRUE.subs({}, default=algebra.FALSE).simplify() == algebra.TRUE
        assert algebra.FALSE.subs({}, default=algebra.TRUE).simplify() == algebra.FALSE

    def test_normalize(self):
        algebra = BooleanAlgebra()

        expr = algebra.parse("a&b")
        assert algebra.dnf(expr) == expr
        assert algebra.cnf(expr) == expr

        expr = algebra.parse("a|b")
        assert algebra.dnf(expr) == expr
        assert algebra.cnf(expr) == expr

        expr = algebra.parse("(a&b)|(c&b)")
        result_dnf = algebra.parse("(a&b)|(b&c)")
        result_cnf = algebra.parse("b&(a|c)")
        assert algebra.dnf(expr) == result_dnf
        assert algebra.cnf(expr) == result_cnf

        expr = algebra.parse("(a|b)&(c|b)")
        result_dnf = algebra.parse("b|(a&c)")
        result_cnf = algebra.parse("(a|b)&(b|c)")
        assert algebra.dnf(expr) == result_dnf
        assert algebra.cnf(expr) == result_cnf

        expr = algebra.parse("((s|a)&(s|b)&(s|c)&(s|d)&(e|c|d))|(a&e&d)")
        result = algebra.normalize(expr, expr.AND)
        expected = algebra.parse("(a|s)&(b|e|s)&(c|d|e)&(c|e|s)&(d|s)")
        assert expected == result

    def test_get_literals_return_all_literals_in_original_order(self):
        alg = BooleanAlgebra()
        exp = alg.parse("a and b or a and c")
        assert [
            alg.Symbol("a"),
            alg.Symbol("b"),
            alg.Symbol("a"),
            alg.Symbol("c"),
        ] == exp.get_literals()

    def test_get_symbols_return_all_symbols_in_original_order(self):
        alg = BooleanAlgebra()
        exp = alg.parse("a and b or True and a and c")
        assert [
            alg.Symbol("a"),
            alg.Symbol("b"),
            alg.Symbol("a"),
            alg.Symbol("c"),
        ] == exp.get_symbols()

    def test_literals_return_set_of_unique_literals(self):
        alg = BooleanAlgebra()
        exp = alg.parse("a and b or a and c")
        assert set([alg.Symbol("a"), alg.Symbol("b"), alg.Symbol("c")]) == exp.literals

    def test_literals_and_negation(self):
        alg = BooleanAlgebra()
        exp = alg.parse("a and not b and not not c")
        assert set([alg.Symbol("a"), alg.parse("not b"), alg.parse("not c")]) == exp.literals

    def test_symbols_and_negation(self):
        alg = BooleanAlgebra()
        exp = alg.parse("a and not b and not not c")
        assert set([alg.Symbol("a"), alg.Symbol("b"), alg.Symbol("c")]) == exp.symbols

    def test_objects_return_set_of_unique_Symbol_objs(self):
        alg = BooleanAlgebra()
        exp = alg.parse("a and b or a and c")
        assert set(["a", "b", "c"]) == exp.objects

    def test_normalize_blowup(self):
        from boolean import AND, NOT, OR
        from collections import defaultdict

        # Subclasses to count calls to simplify
        class CountingNot(NOT):
            def simplify(self):
                counts["CountingNot"] += 1
                return super().simplify()

        class CountingAnd(AND):
            def simplify(self, sort=True):
                counts["CountingAnd"] += 1
                return super().simplify(sort=sort)

        class CountingOr(OR):
            def simplify(self, sort=True):
                counts["CountingOr"] += 1
                return super().simplify(sort=sort)

        counts = defaultdict(int)

        # Real-world example of a complex expression with simple CNF/DNF form.
        # Note this is a more reduced, milder version of the problem, for rapid
        # testing.
        formula = """
        a & (
            (b & c & d & e & f & g)
            | (c & f & g & h & i & j)
            | (c & d & f & g & i & l & o & u)
            | (c & e & f & g & i & p & y & ~v)
            | (c & f & g & i & j & z & ~(c & f & g & i & j & k))
            | (c & f & g & t & ~(b & c & d & e & f & g))
            | (c & f & g & ~t & ~(b & c & d & e & f & g))
        )
        """
        algebra = BooleanAlgebra(
            NOT_class=CountingNot,
            AND_class=CountingAnd,
            OR_class=CountingOr,
        )

        expr = algebra.parse(formula)
        cnf = algebra.cnf(expr)
        assert str(cnf) == "a&c&f&g"
        # We should get exactly this count of calls.
        # before we had a combinatorial explosion
        assert counts == {"CountingAnd": 44, "CountingNot": 193, "CountingOr": 2490}


class BooleanBoolTestCase(unittest.TestCase):
    def test_bool(self):
        algebra = BooleanAlgebra()
        a, b, c = algebra.Symbol("a"), algebra.Symbol("b"), algebra.Symbol("c")
        expr = a & b | c
        self.assertRaises(TypeError, bool, expr.subs({a: algebra.TRUE}))
        self.assertRaises(TypeError, bool, expr.subs({b: algebra.TRUE}))
        self.assertRaises(TypeError, bool, expr.subs({c: algebra.TRUE}))
        self.assertRaises(TypeError, bool, expr.subs({a: algebra.TRUE, b: algebra.TRUE}))
        result = expr.subs({c: algebra.TRUE}, simplify=True)
        result = result.simplify()
        assert result == algebra.TRUE

        result = expr.subs({a: algebra.TRUE, b: algebra.TRUE}, simplify=True)
        result = result.simplify()
        assert result == algebra.TRUE


class CustomSymbolTestCase(unittest.TestCase):
    def test_custom_symbol(self):
        class CustomSymbol(Symbol):
            def __init__(self, name, value="value"):
                self.var = value
                super(CustomSymbol, self).__init__(name)

        try:
            CustomSymbol("a", value="This is A")
        except TypeError as e:
            self.fail(e)


class CallabilityTestCase(unittest.TestCase):
    def test_and(self):
        algebra = BooleanAlgebra()
        exp = algebra.parse("a&b&c")
        for a in [True, False]:
            for b in [True, False]:
                for c in [True, False]:
                    assert exp(a=a, b=b, c=c) == (a and b and c)

    def test_or(self):
        algebra = BooleanAlgebra()
        exp = algebra.parse("a|b|c")
        for a in [True, False]:
            for b in [True, False]:
                for c in [True, False]:
                    assert exp(a=a, b=b, c=c) == (a or b or c)

    def test_not(self):
        algebra = BooleanAlgebra()
        exp = algebra.parse("!a")
        for a in [True, False]:
            assert exp(a=a) == (not a)

    def test_symbol(self):
        algebra = BooleanAlgebra()
        exp = algebra.parse("a")
        for a in [True, False]:
            assert exp(a=a) == a

    def test_composite(self):
        algebra = BooleanAlgebra()
        exp = algebra.parse("!(a|b&(a|!c))")
        for a in [True, False]:
            for b in [True, False]:
                for c in [True, False]:
                    assert exp(a=a, b=b, c=c) == (not (a or b and (a or not c)))

    def test_negate_A_or_B(self):
        algebra = BooleanAlgebra()
        exp = algebra.parse("!(a|b)")
        for a in [True, False]:
            for b in [True, False]:
                assert exp(a=a, b=b) == (not (a or b))
