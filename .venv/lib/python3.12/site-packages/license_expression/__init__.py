#
# Copyright (c) nexB Inc. and others. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
# See http://www.apache.org/licenses/LICENSE-2.0 for the license text.
# See https://github.com/aboutcode-org/license-expression for support or download.
# See https://aboutcode.org for more information about nexB OSS projects.
#
"""
Define a mini language to parse, validate, deduplicate, simplify,
normalize and compare license expressions using a boolean logic engine.

This module supports SPDX and ScanCode license expressions and also accepts other
license naming conventions and license identifiers aliases to recognize and
normalize licenses.

Using boolean logic, license expressions can be tested for equality,
containment, equivalence and can be normalized, deduplicated or simplified.

The main entry point is the Licensing object.
"""

import itertools
import json
import re
import string
from collections import defaultdict
from collections import deque
from collections import namedtuple
from copy import copy
from copy import deepcopy
from functools import total_ordering
from os.path import abspath
from os.path import dirname
from os.path import join

import boolean
from boolean import Expression as LicenseExpression

# note these may not all be used here but are imported here to avoid leaking
# boolean.py constants to callers
from boolean.boolean import PARSE_ERRORS
from boolean.boolean import PARSE_INVALID_EXPRESSION
from boolean.boolean import PARSE_INVALID_NESTING
from boolean.boolean import PARSE_INVALID_OPERATOR_SEQUENCE
from boolean.boolean import PARSE_INVALID_SYMBOL_SEQUENCE
from boolean.boolean import PARSE_UNBALANCED_CLOSING_PARENS
from boolean.boolean import PARSE_UNKNOWN_TOKEN

from boolean.boolean import ParseError
from boolean.boolean import TOKEN_SYMBOL
from boolean.boolean import TOKEN_AND
from boolean.boolean import TOKEN_OR
from boolean.boolean import TOKEN_LPAR
from boolean.boolean import TOKEN_RPAR

from license_expression._pyahocorasick import Trie as AdvancedTokenizer
from license_expression._pyahocorasick import Token

curr_dir = dirname(abspath(__file__))
data_dir = join(curr_dir, "data")
vendored_scancode_licensedb_index_location = join(
    data_dir,
    "scancode-licensedb-index.json",
)

# append new error codes to PARSE_ERRORS by monkey patching
PARSE_EXPRESSION_NOT_UNICODE = 100
if PARSE_EXPRESSION_NOT_UNICODE not in PARSE_ERRORS:
    PARSE_ERRORS[PARSE_EXPRESSION_NOT_UNICODE] = "Expression string must be a string."

PARSE_INVALID_EXCEPTION = 101
if PARSE_INVALID_EXCEPTION not in PARSE_ERRORS:
    PARSE_ERRORS[PARSE_INVALID_EXCEPTION] = (
        "A license exception symbol can only be used as an exception "
        'in a "WITH exception" statement.'
    )

PARSE_INVALID_SYMBOL_AS_EXCEPTION = 102
if PARSE_INVALID_SYMBOL_AS_EXCEPTION not in PARSE_ERRORS:
    PARSE_ERRORS[PARSE_INVALID_SYMBOL_AS_EXCEPTION] = (
        'A plain license symbol cannot be used as an exception in a "WITH symbol" statement.'
    )

PARSE_INVALID_SYMBOL = 103
if PARSE_INVALID_SYMBOL not in PARSE_ERRORS:
    PARSE_ERRORS[PARSE_INVALID_SYMBOL] = "A proper license symbol is needed."


class ExpressionError(Exception):
    pass


class ExpressionParseError(ParseError, ExpressionError):
    pass


# Used for tokenizing
Keyword = namedtuple("Keyword", "value type")
Keyword.__len__ = lambda self: len(self.value)

# id for the "WITH" token which is not a proper boolean symbol but an expression
# symbol
TOKEN_WITH = 10

# keyword types that include operators and parens

KW_LPAR = Keyword("(", TOKEN_LPAR)
KW_RPAR = Keyword(")", TOKEN_RPAR)
KW_AND = Keyword("and", TOKEN_AND)
KW_OR = Keyword("or", TOKEN_OR)
KW_WITH = Keyword("with", TOKEN_WITH)

KEYWORDS = (
    KW_AND,
    KW_OR,
    KW_LPAR,
    KW_RPAR,
    KW_WITH,
)
KEYWORDS_STRINGS = set(kw.value for kw in KEYWORDS)

# mapping of lowercase operator strings to an operator object
OPERATORS = {"and": KW_AND, "or": KW_OR, "with": KW_WITH}

_simple_tokenizer = re.compile(
    r"""
    (?P<symop>[^\s\(\)]+)
     |
    (?P<space>\s+)
     |
    (?P<lpar>\()
     |
    (?P<rpar>\))
    """,
    re.VERBOSE | re.MULTILINE | re.UNICODE,
).finditer


class ExpressionInfo:
    """
    The ExpressionInfo class is returned by Licensing.validate() where it stores
    information about a given license expression passed into
    Licensing.validate().

    The ExpressionInfo class has the following fields:

    - original_expression: str.
        - This is the license expression that was originally passed into
          Licensing.validate()

    - normalized_expression: str.
        - If a valid license expression has been passed into `validate()`,
          then the license expression string will be set in this field.

    - errors: list
        - If there were errors validating a license expression,
          the error messages will be appended here.

    - invalid_symbols: list
        - If the license expression that has been passed into `validate()` has
          license keys that are invalid (either that they are unknown or not used
          in the right context), or the syntax is incorrect because an invalid
          symbol was used, then those symbols will be appended here.
    """

    def __init__(
        self,
        original_expression,
        normalized_expression=None,
        errors=None,
        invalid_symbols=None,
    ):
        self.original_expression = original_expression
        self.normalized_expression = normalized_expression
        self.errors = errors or []
        self.invalid_symbols = invalid_symbols or []

    def __repr__(self):
        return (
            "ExpressionInfo(\n"
            f"    original_expression={self.original_expression!r},\n"
            f"    normalized_expression={self.normalized_expression!r},\n"
            f"    errors={self.errors!r},\n"
            f"    invalid_symbols={self.invalid_symbols!r}\n"
            ")"
        )


class Licensing(boolean.BooleanAlgebra):
    """
    Licensing defines a mini language to parse, validate and compare license
    expressions. This is the main entry point in this library.

    Some of the features are:

    - licenses can be validated against user-provided lists of known licenses
      "symbols" (such as ScanCode licenses or the SPDX list).

    - flexible expression parsing and recognition of licenses (including
      licenses with spaces and keywords (such as AND, OR WITH) or parens in
      their names).

    - in an expression licenses can be more than just identifiers such as short
      or long names with spaces, symbols and even parenthesis.

    - A license can have multiple aliases (such as GPL-2.0, GPLv2 or GPL2) and
      each will be properly recognized when parsing. The expression is rendered
      normalized using the canononical license keys.

    - expressions can be deduplicated, simplified, normalized, sorted and
      compared for containment and/or logical equivalence thanks to a built-in
      boolean logic engine.

    - Once parsed, expressions can be rendered using simple templates (for
      instance to render as HTML links in a web UI).

    For example::

    >>> l = Licensing()
    >>> expr = l.parse(" GPL-2.0 or LGPL-2.1 and mit ")
    >>> expected = 'GPL-2.0 OR (LGPL-2.1 AND mit)'
    >>> assert expected == expr.render('{symbol.key}')

    >>> expected = [
    ...   LicenseSymbol('GPL-2.0'),
    ...   LicenseSymbol('LGPL-2.1'),
    ...   LicenseSymbol('mit')
    ... ]
    >>> assert expected == l.license_symbols(expr)

    >>> symbols = ['GPL-2.0+', 'Classpath', 'BSD']
    >>> l = Licensing(symbols)
    >>> expression = 'GPL-2.0+ with Classpath or (bsd)'
    >>> parsed = l.parse(expression)
    >>> expected = 'GPL-2.0+ WITH Classpath OR BSD'
    >>> assert expected == parsed.render('{symbol.key}')

    >>> expected = [
    ...   LicenseSymbol('GPL-2.0+'),
    ...   LicenseSymbol('Classpath'),
    ...   LicenseSymbol('BSD')
    ... ]
    >>> assert expected == l.license_symbols(parsed)
    >>> assert expected == l.license_symbols(expression)
    """

    def __init__(self, symbols=tuple(), quiet=True):
        """
        Initialize a Licensing with an optional ``symbols`` sequence of
        LicenseSymbol or LicenseSymbol-like objects or license key strings. If
        provided and this list data is invalid, raise a ValueError. Print
        warning and errors found in the symbols unless ``quiet`` is True.
        """
        super(Licensing, self).__init__(
            Symbol_class=LicenseSymbol,
            AND_class=AND,
            OR_class=OR,
        )

        # FIXME: this should be instead a super class of all symbols
        self.LicenseSymbol = self.Symbol
        # LicenseWithExceptionSymbol does not get its internal Expressions mapped durring BooleanAlgebra init
        # have to set it after the fact
        tf_nao = {
            "TRUE": self.TRUE,
            "FALSE": self.FALSE,
            "NOT": self.NOT,
            "AND": self.AND,
            "OR": self.OR,
            "Symbol": self.Symbol,
        }

        for name, value in tf_nao.items():
            setattr(LicenseWithExceptionSymbol, name, value)

        symbols = symbols or tuple()

        if symbols:
            symbols = tuple(as_symbols(symbols))
            warns, errors = validate_symbols(symbols)

            if warns and not quiet:
                for w in warns:
                    print(w)

            if errors and not quiet:
                for e in errors:
                    print(e)

            if errors:
                raise ValueError("\n".join(warns + errors))

        # mapping of known symbol key to symbol for reference
        self.known_symbols = {symbol.key: symbol for symbol in symbols}

        # mapping of known symbol lowercase key to symbol for reference
        self.known_symbols_lowercase = {symbol.key.lower(): symbol for symbol in symbols}

        # Aho-Corasick automaton-based Advanced Tokenizer
        self.advanced_tokenizer = None

    def is_equivalent(self, expression1, expression2, **kwargs):
        """
        Return True if both ``expression1`` and ``expression2``
        LicenseExpression objects are equivalent. If a string is provided, it
        will be parsed and simplified. Extra ``kwargs`` are passed down to the
        parse() function.
        Raise ExpressionError on parse errors.
        """
        ex1 = self._parse_and_simplify(expression1, **kwargs)
        ex2 = self._parse_and_simplify(expression2, **kwargs)
        return ex1 == ex2

    def contains(self, expression1, expression2, **kwargs):
        """
        Return True if ``expression1`` contains ``expression2``. where each
        expression is either a string or a LicenseExpression object. If a string
        is provided, it will be parsed and simplified.

        Extra ``kwargs`` are passed down to the parse() function.
        """
        ex1 = self._parse_and_simplify(expression1, **kwargs)
        ex2 = self._parse_and_simplify(expression2, **kwargs)
        return ex2 in ex1

    def _parse_and_simplify(self, expression, **kwargs):
        expression = self.parse(expression, **kwargs)
        if expression is None:
            return None

        if not isinstance(expression, LicenseExpression):
            raise TypeError(f"expression must be LicenseExpression object: {expression!r}")

        return expression.simplify()

    def license_symbols(self, expression, unique=True, decompose=True, **kwargs):
        """
        Return a list of LicenseSymbol objects used in an expression in the same
        order as they first appear in the expression tree.

        ``expression`` is either a string or a LicenseExpression object.
        If a string is provided, it will be parsed.

        If ``unique`` is True only return unique symbols.

        If ``decompose`` is True then composite LicenseWithExceptionSymbol
        instances are not returned directly; instead their underlying license
        and exception symbols are returned.

        Extra ``kwargs`` are passed down to the parse() function.

        For example:
        >>> l = Licensing()
        >>> expected = [
        ...   LicenseSymbol('GPL-2.0'),
        ...   LicenseSymbol('LGPL-2.1+')
        ... ]
        >>> result = l.license_symbols(l.parse('GPL-2.0 or LGPL-2.1+'))
        >>> assert expected == result
        """
        expression = self.parse(expression, **kwargs)
        if expression is None:
            return []
        symbols = (s for s in expression.get_literals() if isinstance(s, BaseSymbol))
        if decompose:
            symbols = itertools.chain.from_iterable(s.decompose() for s in symbols)
        if unique:
            symbols = ordered_unique(symbols)
        return list(symbols)

    def primary_license_symbol(self, expression, decompose=True, **kwargs):
        """
        Return the left-most license symbol of an ``expression`` or None.
        ``expression`` is either a string or a LicenseExpression object.

        If ``decompose`` is True, only the left-hand license symbol of a
        decomposed LicenseWithExceptionSymbol symbol will be returned if this is
        the left most member. Otherwise a composite LicenseWithExceptionSymbol
        is returned in this case.

        Extra ``kwargs`` are passed down to the parse() function.
        """
        symbols = self.license_symbols(expression, decompose=decompose, **kwargs)
        if symbols:
            return symbols[0]

    def primary_license_key(self, expression, **kwargs):
        """
        Return the left-most license key of an ``expression`` or None. The
        underlying symbols are decomposed.

        ``expression`` is either a string or a LicenseExpression object.

        Extra ``kwargs`` are passed down to the parse() function.
        """
        prim = self.primary_license_symbol(
            expression=expression,
            decompose=True,
            **kwargs,
        )
        if prim:
            return prim.key

    def license_keys(self, expression, unique=True, **kwargs):
        """
        Return a list of licenses keys used in an ``expression`` in the same
        order as they first appear in the expression. ``expression`` is either a
        string or a LicenseExpression object.

        If ``unique`` is True only return unique symbols.
        Extra ``kwargs`` are passed down to the parse() function.

        For example:
        >>> l = Licensing()
        >>> expr = ' GPL-2.0 and mit+ with blabla and mit or LGPL-2.1 and mit and mit+ with GPL-2.0'
        >>> expected = ['GPL-2.0', 'mit+', 'blabla', 'mit', 'LGPL-2.1']
        >>> assert expected == l.license_keys(l.parse(expr))
        """
        symbols = self.license_symbols(
            expression=expression,
            unique=False,
            decompose=True,
            **kwargs,
        )
        return self._keys(symbols, unique)

    def _keys(self, symbols, unique=True):
        keys = [ls.key for ls in symbols]
        # note: we only apply this on bare keys strings as we can have the same
        # symbol used as symbol or exception if we are not in strict mode
        if unique:
            keys = ordered_unique(keys)
        return keys

    def unknown_license_symbols(self, expression, unique=True, **kwargs):
        """
        Return a list of unknown license symbols used in an ``expression`` in
        the same order as they first appear in the ``expression``.
        ``expression`` is either a string or a LicenseExpression object.

        If ``unique`` is True only return unique symbols.
        Extra ``kwargs`` are passed down to the parse() function.
        """
        symbols = self.license_symbols(
            expression=expression,
            unique=unique,
            decompose=True,
            **kwargs,
        )
        return [ls for ls in symbols if not ls.key in self.known_symbols]

    def unknown_license_keys(self, expression, unique=True, **kwargs):
        """
        Return a list of unknown licenses keys used in an ``expression`` in the
        same order as they first appear in the ``expression``.

        ``expression`` is either a string or a LicenseExpression object.
        If a string is provided, it will be parsed.

        If ``unique`` is True only return unique keys.
        Extra ``kwargs`` are passed down to the parse() function.
        """
        symbols = self.unknown_license_symbols(
            expression=expression,
            unique=False,
            **kwargs,
        )
        return self._keys(symbols, unique)

    def validate_license_keys(self, expression):
        unknown_keys = self.unknown_license_keys(expression, unique=True)
        if unknown_keys:
            msg = "Unknown license key(s): {}".format(", ".join(unknown_keys))
            raise ExpressionError(msg)

    def parse(self, expression, validate=False, strict=False, simple=False, **kwargs):
        """
        Return a new license LicenseExpression object by parsing a license
        ``expression``. Check that the ``expression`` syntax is valid and
        raise an ExpressionError or an ExpressionParseError on errors.

        Return None for empty expressions. ``expression`` is either a string or
        a LicenseExpression object. If ``expression`` is a LicenseExpression it
        is returned as-is.

        Symbols are always recognized from known Licensing symbols if `symbols`
        were provided at Licensing creation time: each license and exception is
        recognized from known license keys (and from aliases for a symbol if
        available).

        If ``validate`` is True and a license is unknown, an ExpressionError
        error is raised with a message listing the unknown license keys.

        If ``validate`` is False, no error is raised if the ``expression``
        syntax is correct. You can call further call the
        `unknown_license_keys()` or `unknown_license_symbols()` methods to get
        unknown license keys or symbols found in the parsed LicenseExpression.

        If ``strict`` is True, an ExpressionError will be raised if in a
        "WITH" expression such as "XXX with ZZZ" if the XXX symbol has
        `is_exception` set to True or the YYY symbol has `is_exception` set to
        False. This checks that symbols are used strictly as intended in a
        "WITH" subexpression using a license on the left and an exception on thr
        right.

        If ``simple`` is True, parsing will use a simple tokenizer that assumes
        that license symbols are all license keys and do not contain spaces.

        For example:
        >>> expression = 'EPL-1.0 and Apache-1.1 OR GPL-2.0 with Classpath-exception'
        >>> parsed = Licensing().parse(expression)
        >>> expected = '(EPL-1.0 AND Apache-1.1) OR GPL-2.0 WITH Classpath-exception'
        >>> assert expected == parsed.render(template='{symbol.key}')
        """
        if expression is None:
            return

        if isinstance(expression, LicenseExpression):
            return expression

        if isinstance(expression, bytes):
            try:
                expression = str(expression)
            except:
                ext = type(expression)
                raise ExpressionError(f"expression must be a string and not: {ext!r}")

        if not isinstance(expression, str):
            ext = type(expression)
            raise ExpressionError(f"expression must be a string and not: {ext!r}")

        if not expression or not expression.strip():
            return
        try:
            # this will raise a ParseError on errors
            tokens = list(
                self.tokenize(
                    expression=expression,
                    strict=strict,
                    simple=simple,
                )
            )
            expression = super(Licensing, self).parse(tokens)

        except ParseError as e:
            raise ExpressionParseError(
                token_type=e.token_type,
                token_string=e.token_string,
                position=e.position,
                error_code=e.error_code,
            ) from e

        if not isinstance(expression, LicenseExpression):
            raise ExpressionError("expression must be a LicenseExpression once parsed.")

        if validate:
            self.validate_license_keys(expression)

        return expression

    def tokenize(self, expression, strict=False, simple=False):
        """
        Return an iterable of 3-tuple describing each token given an
        ``expression`` string. See boolean.BooleanAlgreba.tokenize() for API
        details.

        This 3-tuple contains these items: (token, token string, position):
        - token: either a Symbol instance or one of TOKEN_* token types..
        - token string: the original token string.
        - position: the starting index of the token string in the `expr` string.

        If ``strict`` is True, additional exceptions will be raised in a
        expression such as "XXX with ZZZ" if the XXX symbol has is_exception`
        set to True or the ZZZ symbol has `is_exception` set to False.

        If ``simple`` is True, use a simple tokenizer that assumes that license
        symbols are all license keys that do not contain spaces.
        """
        if not expression:
            return

        if not isinstance(expression, str):
            raise ParseError(error_code=PARSE_EXPRESSION_NOT_UNICODE)

        if simple:
            tokens = self.simple_tokenizer(expression)
        else:
            advanced_tokenizer = self.get_advanced_tokenizer()
            tokens = advanced_tokenizer.tokenize(expression)

        # Assign symbol for unknown tokens
        tokens = build_symbols_from_unknown_tokens(tokens)

        # skip whitespace-only tokens
        tokens = (t for t in tokens if t.string and t.string.strip())

        # create atomic LicenseWithExceptionSymbol from WITH subexpressions
        tokens = replace_with_subexpression_by_license_symbol(tokens, strict)

        # finally yield the actual args expected by the boolean parser
        for token in tokens:
            pos = token.start
            token_string = token.string
            token_value = token.value

            if isinstance(token_value, BaseSymbol):
                token_obj = token_value
            elif isinstance(token_value, Keyword):
                token_obj = token_value.type
            else:
                raise ParseError(error_code=PARSE_INVALID_EXPRESSION)

            yield token_obj, token_string, pos

    def get_advanced_tokenizer(self):
        """
        Return an AdvancedTokenizer instance for this Licensing either cached or
        created as needed.

        If symbols were provided when this Licensing object was created, the
        tokenizer will recognize known symbol keys and aliases (ignoring case)
        when tokenizing expressions.

        A license symbol is any string separated by keywords and parens (and it
        can include spaces).
        """
        if self.advanced_tokenizer is not None:
            return self.advanced_tokenizer

        self.advanced_tokenizer = tokenizer = AdvancedTokenizer()

        add_item = tokenizer.add
        for keyword in KEYWORDS:
            add_item(keyword.value, keyword)

        # self.known_symbols has been created at Licensing initialization time
        # and is already validated and trusted here
        for key, symbol in self.known_symbols.items():
            # always use the key even if there are no aliases.
            add_item(key, symbol)
            aliases = getattr(symbol, "aliases", [])
            for alias in aliases:
                # normalize spaces for each alias. The AdvancedTokenizer will
                # lowercase them
                if alias:
                    alias = " ".join(alias.split())
                    add_item(alias, symbol)

        tokenizer.make_automaton()
        return tokenizer

    def advanced_tokenizer(self, expression):
        """
        Return an iterable of Token from an ``expression`` string.
        """
        tokenizer = self.get_advanced_tokenizer()
        return tokenizer.tokenize(expression)

    def simple_tokenizer(self, expression):
        """
        Return an iterable of Token from an ``expression`` string.

        The split is done on spaces, keywords and parens. Anything else is a
        symbol token, e.g. a typically license key or license id (that contains
        no spaces or parens).

        If symbols were provided when this Licensing object was created, the
        tokenizer will recognize known symbol keys (ignoring case) when
        tokenizing expressions.
        """

        symbols = self.known_symbols_lowercase or {}

        for match in _simple_tokenizer(expression):
            if not match:
                continue
            # set start and end as string indexes
            start, end = match.span()
            end = end - 1
            match_getter = match.groupdict().get

            space = match_getter("space")
            if space:
                yield Token(start, end, space, None)

            lpar = match_getter("lpar")
            if lpar:
                yield Token(start, end, lpar, KW_LPAR)

            rpar = match_getter("rpar")
            if rpar:
                yield Token(start, end, rpar, KW_RPAR)

            sym_or_op = match_getter("symop")
            if sym_or_op:
                sym_or_op_lower = sym_or_op.lower()

                operator = OPERATORS.get(sym_or_op_lower)
                if operator:
                    yield Token(start, end, sym_or_op, operator)
                else:
                    sym = symbols.get(sym_or_op_lower)
                    if not sym:
                        sym = LicenseSymbol(key=sym_or_op)
                    yield Token(start, end, sym_or_op, sym)

    def dedup(self, expression):
        """
        Return a deduplicated LicenseExpression given a license ``expression``
        string or LicenseExpression object.

        The deduplication process is similar to simplification but is
        specialized for working with license expressions. Simplification is
        otherwise a generic boolean operation that is not aware of the specifics
        of license expressions.

        The deduplication:

        - Does not sort the licenses of sub-expression in an expression. They
          stay in the same order as in the original expression.

        - Choices (as in "MIT or GPL") are kept as-is and not treated as
          simplifiable. This avoids droping important choice options in complex
          expressions which is never desirable.

        """
        exp = self.parse(expression)
        expressions = []
        for arg in exp.args:
            if isinstance(
                arg,
                (
                    self.AND,
                    self.OR,
                ),
            ):
                # Run this recursive function if there is another AND/OR
                # expression and add the expression to the expressions list.
                expressions.append(self.dedup(arg))
            else:
                expressions.append(arg)

        if isinstance(exp, BaseSymbol):
            deduped = exp
        elif isinstance(
            exp,
            (
                self.AND,
                self.OR,
            ),
        ):
            relation = exp.__class__.__name__
            deduped = combine_expressions(
                expressions,
                relation=relation,
                unique=True,
                licensing=self,
            )
        else:
            raise ExpressionError(f"Unknown expression type: {expression!r}")
        return deduped

    def validate(self, expression, strict=True, **kwargs):
        """
        Return a ExpressionInfo object that contains information about
        the validation of an ``expression``  license expression string.

        If the syntax and license keys of ``expression`` is valid, then
        `ExpressionInfo.normalized_license_expression` is set.

        If an error was encountered when validating ``expression``,
        `ExpressionInfo.errors` will be populated with strings containing the
        error message that has occured. If an error has occured due to unknown
        license keys or an invalid license symbol, the offending keys or symbols
        will be present in `ExpressionInfo.invalid_symbols`

        If ``strict`` is True, validation error messages will be included if in
        a "WITH" expression such as "XXX with ZZZ" if the XXX symbol has
        `is_exception` set to True or the YYY symbol has `is_exception` set to
        False. This checks that exception symbols are used strictly as intended
        on the right side of a "WITH" statement.
        """
        expression_info = ExpressionInfo(original_expression=str(expression))

        # Check `expression` type and syntax
        try:
            parsed_expression = self.parse(expression, strict=strict)
        except ExpressionError as e:
            expression_info.errors.append(str(e))
            expression_info.invalid_symbols.append(e.token_string)
            return expression_info

        # Check `expression` keys (validate)
        try:
            self.validate_license_keys(expression)
        except ExpressionError as e:
            expression_info.errors.append(str(e))
            unknown_keys = self.unknown_license_keys(expression)
            expression_info.invalid_symbols.extend(unknown_keys)
            return expression_info

        # If we have not hit an exception, set `normalized_expression` in
        # `expression_info` only if we did not encounter any errors
        # along the way
        if not expression_info.errors and not expression_info.invalid_symbols:
            expression_info.normalized_expression = str(parsed_expression)
        return expression_info


def get_scancode_licensing(license_index_location=vendored_scancode_licensedb_index_location):
    """
    Return a Licensing object using ScanCode license keys loaded from a
    ``license_index_location`` location of a license db JSON index files
    See https://scancode-licensedb.aboutcode.org/index.json
    """
    return build_licensing(get_license_index(license_index_location))


def get_spdx_licensing(license_index_location=vendored_scancode_licensedb_index_location):
    """
    Return a Licensing object using SPDX license keys loaded from a
    ``license_index_location`` location of a license db JSON index files
    See https://scancode-licensedb.aboutcode.org/index.json
    """
    return build_spdx_licensing(get_license_index(license_index_location))


def get_license_index(license_index_location=vendored_scancode_licensedb_index_location):
    """
    Return a list of mappings that contain license key information from
    ``license_index_location``

    The default value of `license_index_location` points to a vendored copy
    of the license index from https://scancode-licensedb.aboutcode.org/
    """
    with open(license_index_location) as f:
        return json.load(f)


def load_licensing_from_license_index(license_index):
    """
    Return a Licensing object that has been loaded with license keys and
    attributes from a ``license_index`` list of license mappings.
    """
    syms = [LicenseSymbol(**l) for l in license_index]
    return Licensing(syms)


def build_licensing(license_index):
    """
    Return a Licensing object that has been loaded with license keys and
    attributes from a ``license_index`` list of simple ScanCode license mappings.
    """
    lics = [
        {
            "key": l.get("license_key", ""),
            "is_deprecated": l.get("is_deprecated", False),
            "is_exception": l.get("is_exception", False),
        }
        for l in license_index
    ]
    return load_licensing_from_license_index(lics)


def build_spdx_licensing(license_index):
    """
    Return a Licensing object that has been loaded with license keys and
    attributes from a ``license_index`` list of simple SPDX license mappings.
    """
    # Massage data such that SPDX license key is the primary license key
    lics = [
        {
            "key": l.get("spdx_license_key", ""),
            "aliases": l.get("other_spdx_license_keys", []),
            "is_deprecated": l.get("is_deprecated", False),
            "is_exception": l.get("is_exception", False),
        }
        for l in license_index
        if l.get("spdx_license_key")
    ]
    return load_licensing_from_license_index(lics)


def build_symbols_from_unknown_tokens(tokens):
    """
    Yield Token given a ``token`` sequence of Token replacing unmatched
    contiguous tokens by a single token with a LicenseSymbol.
    """
    tokens = list(tokens)

    unmatched = deque()

    def build_token_with_symbol():
        """
        Build and return a new Token from accumulated unmatched tokens or None.
        """
        if not unmatched:
            return
        # strip trailing spaces
        trailing_spaces = []
        while unmatched and not unmatched[-1].string.strip():
            trailing_spaces.append(unmatched.pop())

        if unmatched:
            string = " ".join(t.string for t in unmatched if t.string.strip())
            start = unmatched[0].start
            end = unmatched[-1].end
            toksym = LicenseSymbol(string)
            unmatched.clear()
            yield Token(start, end, string, toksym)

        for ts in trailing_spaces:
            yield ts

    for tok in tokens:
        if tok.value:
            for symtok in build_token_with_symbol():
                yield symtok
            yield tok
        else:
            if not unmatched and not tok.string.strip():
                # skip leading spaces
                yield tok
            else:
                unmatched.append(tok)

    # end remainders
    for symtok in build_token_with_symbol():
        yield symtok


def build_token_groups_for_with_subexpression(tokens):
    """
    Yield tuples of Token given a ``tokens`` sequence of Token such that:
     - all "XXX WITH YYY" sequences of 3 tokens are grouped in a three-tuple
     - single tokens are just wrapped in a tuple for consistency.
    """

    # if n-1 is sym, n is with and n+1 is sym: yield this as a group for a with
    # exp otherwise: yield each single token as a group

    tokens = list(tokens)

    # check three contiguous tokens that may form "lic WITh exception" sequence
    triple_len = 3

    # shortcut if there are no grouping possible
    if len(tokens) < triple_len:
        for tok in tokens:
            yield (tok,)
        return

    # accumulate three contiguous tokens
    triple = deque()
    triple_popleft = triple.popleft
    triple_clear = triple.clear
    tripple_append = triple.append

    for tok in tokens:
        if len(triple) == triple_len:
            if is_with_subexpression(triple):
                yield tuple(triple)
                triple_clear()
            else:
                prev_tok = triple_popleft()
                yield (prev_tok,)
        tripple_append(tok)

    # end remainders
    if triple:
        if len(triple) == triple_len and is_with_subexpression(triple):
            yield tuple(triple)
        else:
            for tok in triple:
                yield (tok,)


def is_with_subexpression(tokens_tripple):
    """
    Return True if a ``tokens_tripple`` Token tripple is a "WITH" license sub-
    expression.
    """
    lic, wit, exc = tokens_tripple
    return (
        isinstance(lic.value, LicenseSymbol)
        and wit.value == KW_WITH
        and isinstance(exc.value, LicenseSymbol)
    )


def replace_with_subexpression_by_license_symbol(tokens, strict=False):
    """
    Given a ``tokens`` iterable of Token, yield updated Token(s) replacing any
    "XXX WITH ZZZ" subexpression by a LicenseWithExceptionSymbol symbol.

    Check validity of WITH subexpessions and raise ParseError on errors.

    If ``strict`` is True also raise ParseError if the left hand side
    LicenseSymbol has `is_exception` True or if the right hand side
    LicenseSymbol has `is_exception` False.
    """
    token_groups = build_token_groups_for_with_subexpression(tokens)

    for token_group in token_groups:
        len_group = len(token_group)

        if not len_group:
            # This should never happen
            continue

        if len_group == 1:
            # a single token
            token = token_group[0]
            tval = token.value

            if isinstance(tval, Keyword):
                if tval.type == TOKEN_WITH:
                    # keyword
                    # a single group cannot be a single 'WITH' keyword:
                    # this is an error that we catch and raise here.
                    raise ParseError(
                        token_type=TOKEN_WITH,
                        token_string=token.string,
                        position=token.start,
                        error_code=PARSE_INVALID_EXPRESSION,
                    )

            elif isinstance(tval, LicenseSymbol):
                if strict and tval.is_exception:
                    raise ParseError(
                        token_type=TOKEN_SYMBOL,
                        token_string=token.string,
                        position=token.start,
                        error_code=PARSE_INVALID_EXCEPTION,
                    )

            else:
                # this should not be possible by design
                raise Exception(f"Licensing.tokenize is internally confused...: {tval!r}")

            yield token
            continue

        if len_group != 3:
            # this should never happen
            string = " ".join([tok.string for tok in token_group])
            start = token_group[0].start
            raise ParseError(
                token_type=TOKEN_SYMBOL,
                token_string=string,
                position=start,
                error_code=PARSE_INVALID_EXPRESSION,
            )

        # from now on we have a tripple of tokens: a WITH sub-expression such as
        # "A with B" seq of three tokens
        lic_token, WITH, exc_token = token_group

        lic = lic_token.string
        exc = exc_token.string
        WITH = WITH.string.strip()
        token_string = f"{lic} {WITH} {exc}"

        # the left hand side license symbol
        lic_sym = lic_token.value

        # this should not happen
        if not isinstance(lic_sym, LicenseSymbol):
            raise ParseError(
                token_type=TOKEN_SYMBOL,
                token_string=lic_token.string,
                position=lic_token.start,
                error_code=PARSE_INVALID_SYMBOL,
            )

        if strict and lic_sym.is_exception:
            raise ParseError(
                token_type=TOKEN_SYMBOL,
                token_string=lic_token.string,
                position=lic_token.start,
                error_code=PARSE_INVALID_EXCEPTION,
            )

        # the right hand side exception symbol
        exc_sym = exc_token.value

        if not isinstance(exc_sym, LicenseSymbol):
            raise ParseError(
                token_type=TOKEN_SYMBOL,
                token_string=lic_sym.string,
                position=lic_sym.start,
                error_code=PARSE_INVALID_SYMBOL,
            )

        if strict and not exc_sym.is_exception:
            raise ParseError(
                token_type=TOKEN_SYMBOL,
                token_string=exc_token.string,
                position=exc_token.start,
                error_code=PARSE_INVALID_SYMBOL_AS_EXCEPTION,
            )

        lic_exc_sym = LicenseWithExceptionSymbol(
            license_symbol=lic_sym,
            exception_symbol=exc_sym,
            strict=strict,
        )

        token = Token(
            start=lic_token.start,
            end=exc_token.end,
            string=token_string,
            value=lic_exc_sym,
        )
        yield token


class Renderable(object):
    """
    An interface for renderable objects.
    """

    def render(self, template="{symbol.key}", *args, **kwargs):
        """
        Return a formatted string rendering for this expression using the
        ``template`` format string to render each license symbol. The variables
        available are `symbol.key` and any other attribute attached to a
        LicenseSymbol-like instance; a custom ``template`` can be provided to
        handle custom rendering such as HTML.

        For symbols that hold multiple licenses (e.g. in a "XXX WITH YYY"
        statement) the template is applied to each symbol individually.

        Note that when render() is called the ``*args`` and ``**kwargs`` are
        passed down recursively to any Renderable object render() method.
        """
        return NotImplementedError

    def render_as_readable(self, template="{symbol.key}", *args, **kwargs):
        """
        Return a formatted string rendering for this expression using the
        ``template`` format string to render each symbol.  Add extra parenthesis
        around "WITH" sub-expressions such as in "(XXX WITH YYY)"for improved
        readbility. See ``render()`` for other arguments.
        """
        if isinstance(self, LicenseWithExceptionSymbol):
            return self.render(template=template, wrap_with_in_parens=False, *args, **kwargs)

        return self.render(template=template, wrap_with_in_parens=True, *args, **kwargs)


class BaseSymbol(Renderable, boolean.Symbol):
    """
    A base class for all symbols.
    """

    def decompose(self):
        """
        Yield the underlying symbols of this symbol.
        """
        raise NotImplementedError

    def __contains__(self, other):
        """
        Test if the ``other`` symbol is contained in this symbol.
        """
        if not isinstance(other, BaseSymbol):
            return False

        if self == other:
            return True

        return any(mine == other for mine in self.decompose())


# validate license keys
is_valid_license_key = re.compile(r"^[-:\w\s\.\+]+$", re.UNICODE).match


# TODO: we need to implement comparison by hand instead
@total_ordering
class LicenseSymbol(BaseSymbol):
    """
    A LicenseSymbol represents a license key or identifier as used in a license
    expression.
    """

    def __init__(
        self, key, aliases=tuple(), is_deprecated=False, is_exception=False, *args, **kwargs
    ):
        if not key:
            raise ExpressionError(f"A license key cannot be empty: {key!r}")

        if not isinstance(key, str):
            if isinstance(key, bytes):
                try:
                    key = str(key)
                except:
                    raise ExpressionError(f"A license key must be a string: {key!r}")
            else:
                raise ExpressionError(f"A license key must be a string: {key!r}")

        key = key.strip()

        if not key:
            raise ExpressionError(f"A license key cannot be blank: {key!r}")

        # note: key can contain spaces
        if not is_valid_license_key(key):
            raise ExpressionError(
                "Invalid license key: the valid characters are: letters and "
                "numbers, underscore, dot, colon or hyphen signs and "
                f"spaces: {key!r}"
            )

        # normalize spaces
        key = " ".join(key.split())

        if key.lower() in KEYWORDS_STRINGS:
            raise ExpressionError(
                'Invalid license key: a key cannot be a reserved keyword: "or",'
                f' "and" or "with": {key!r}'
            )

        self.key = key

        if aliases and not isinstance(
            aliases,
            (
                list,
                tuple,
            ),
        ):
            raise TypeError(
                f"License aliases: {aliases!r} must be a sequence and not: {type(aliases)}."
            )
        self.aliases = aliases and tuple(aliases) or tuple()
        self.is_deprecated = is_deprecated
        self.is_exception = is_exception

        # super only know about a single "obj" object.
        super(LicenseSymbol, self).__init__(self.key)

    def decompose(self):
        """
        Return an iterable of the underlying license symbols for this symbol.
        """
        yield self

    def __hash__(self, *args, **kwargs):
        return hash((self.key, self.is_exception))

    def __eq__(self, other):
        if self is other:
            return True

        if not (isinstance(other, self.__class__) or self.symbol_like(other)):
            return False

        return self.key == other.key and self.is_exception == other.is_exception

    def __ne__(self, other):
        if self is other:
            return False

        if not (isinstance(other, self.__class__) or self.symbol_like(other)):
            return True

        return self.key != other.key or self.is_exception != other.is_exception

    def __lt__(self, other):
        if isinstance(
            other,
            (LicenseSymbol, LicenseWithExceptionSymbol, LicenseSymbolLike),
        ):
            return str(self) < str(other)
        else:
            return NotImplemented

    __nonzero__ = __bool__ = lambda s: True

    def render(self, template="{symbol.key}", *args, **kwargs):
        return template.format(symbol=self)

    def __str__(self):
        return self.key

    def __len__(self):
        return len(self.key)

    def __repr__(self):
        cls = self.__class__.__name__
        key = self.key
        aliases = self.aliases and f"aliases={self.aliases!r}, " or ""
        is_exception = self.is_exception
        return f"{cls}({key!r}, {aliases}is_exception={is_exception!r})"

    def __copy__(self):
        return LicenseSymbol(
            key=self.key,
            aliases=self.aliases and tuple(self.aliases) or tuple(),
            is_exception=self.is_exception,
        )

    @classmethod
    def symbol_like(cls, symbol):
        """
        Return True if ``symbol`` is a symbol-like object with its essential
        attributes.
        """
        return hasattr(symbol, "key") and hasattr(symbol, "is_exception")


# TODO: we need to implement comparison by hand instead
@total_ordering
class LicenseSymbolLike(LicenseSymbol):
    """
    A LicenseSymbolLike object wraps a symbol-like object to expose it's
    LicenseSymbol behavior.
    """

    def __init__(self, symbol_like, *args, **kwargs):
        if not self.symbol_like(symbol_like):
            raise ExpressionError(f"Not a symbol-like object: {symbol_like!r}")

        self.wrapped = symbol_like
        super(LicenseSymbolLike, self).__init__(key=self.wrapped.key, *args, **kwargs)

        self.is_exception = self.wrapped.is_exception
        self.aliases = getattr(self.wrapped, "aliases", tuple())

        # can we delegate rendering to a render method of the wrapped object?
        # we can if we have a .render() callable on the wrapped object.
        self._render = None
        renderer = getattr(symbol_like, "render", None)
        if callable(renderer):
            self._render = renderer

    def __copy__(self):
        return LicenseSymbolLike(symbol_like=self.wrapped)

    def render(self, template="{symbol.key}", *args, **kwargs):
        if self._render:
            return self._render(template, *args, **kwargs)

        return super(LicenseSymbolLike, self).render(template, *args, **kwargs)

    __nonzero__ = __bool__ = lambda s: True

    def __hash__(self, *args, **kwargs):
        return hash((self.key, self.is_exception))

    def __eq__(self, other):
        if self is other:
            return True
        if not (isinstance(other, self.__class__) or self.symbol_like(other)):
            return False
        return self.key == other.key and self.is_exception == other.is_exception

    def __ne__(self, other):
        if self is other:
            return False
        if not (isinstance(other, self.__class__) or self.symbol_like(other)):
            return True
        return self.key != other.key or self.is_exception != other.is_exception

    def __lt__(self, other):
        if isinstance(other, (LicenseSymbol, LicenseWithExceptionSymbol, LicenseSymbolLike)):
            return str(self) < str(other)
        else:
            return NotImplemented


# TODO: we need to implement comparison by hand instead
@total_ordering
class LicenseWithExceptionSymbol(BaseSymbol):
    """
    A LicenseWithExceptionSymbol represents a license with a "WITH" keyword and
    a license exception such as the Classpath exception. When used in a license
    expression, this is treated as a single Symbol. It holds two LicenseSymbols
    objects: one for the left-hand side license proper and one for the right-
    hand side exception to the license and deals with the specifics of
    resolution, validation and representation.
    """

    def __init__(self, license_symbol, exception_symbol, strict=False, *args, **kwargs):
        """
        Initialize a new LicenseWithExceptionSymbol from a ``license_symbol``
        and a ``exception_symbol`` symbol-like objects.

        Raise a ExpressionError exception if ``strict`` is True and either:
        - ``license_symbol``.is_exception is True
        - ``exception_symbol``.is_exception is not True
        """
        if not LicenseSymbol.symbol_like(license_symbol):
            raise ExpressionError(
                f"license_symbol must be a LicenseSymbol-like object: {license_symbol!r}",
            )

        if strict and license_symbol.is_exception:
            raise ExpressionError(
                'license_symbol cannot be an exception with the "is_exception" '
                f"attribute set to True:{license_symbol!r}",
            )

        if not LicenseSymbol.symbol_like(exception_symbol):
            raise ExpressionError(
                f"exception_symbol must be a LicenseSymbol-like object: {exception_symbol!r}",
            )

        if strict and not exception_symbol.is_exception:
            raise ExpressionError(
                'exception_symbol must be an exception with "is_exception" '
                f"set to True: {exception_symbol!r}",
            )

        self.license_symbol = license_symbol
        self.exception_symbol = exception_symbol

        super(LicenseWithExceptionSymbol, self).__init__(str(self))

    def __copy__(self):
        return LicenseWithExceptionSymbol(
            license_symbol=copy(self.license_symbol),
            exception_symbol=copy(self.exception_symbol),
        )

    def decompose(self):
        yield self.license_symbol
        yield self.exception_symbol

    def render(self, template="{symbol.key}", wrap_with_in_parens=False, *args, **kwargs):
        """
        Return a formatted "WITH" expression. If ``wrap_with_in_parens``, wrap
        the expression in parens as in "(XXX WITH YYY)".
        """
        lic = self.license_symbol.render(template, *args, **kwargs)
        exc = self.exception_symbol.render(template, *args, **kwargs)
        rend = f"{lic} WITH {exc}"
        if wrap_with_in_parens:
            rend = f"({rend})"
        return rend

    def __hash__(self, *args, **kwargs):
        return hash(
            (
                self.license_symbol,
                self.exception_symbol,
            )
        )

    def __eq__(self, other):
        if self is other:
            return True

        if not isinstance(other, self.__class__):
            return False

        return (
            self.license_symbol == other.license_symbol
            and self.exception_symbol == other.exception_symbol
        )

    def __ne__(self, other):
        if self is other:
            return False

        if not isinstance(other, self.__class__):
            return True

        return not (
            self.license_symbol == other.license_symbol
            and self.exception_symbol == other.exception_symbol
        )

    def __lt__(self, other):
        if isinstance(other, (LicenseSymbol, LicenseWithExceptionSymbol, LicenseSymbolLike)):
            return str(self) < str(other)
        else:
            return NotImplemented

    __nonzero__ = __bool__ = lambda s: True

    def __str__(self):
        return f"{self.license_symbol.key} WITH {self.exception_symbol.key}"

    def __repr__(self):
        cls = self.__class__.__name__
        data = dict(cls=self.__class__.__name__)
        data.update(self.__dict__)
        return (
            f"{cls}("
            f"license_symbol={self.license_symbol!r}, "
            f"exception_symbol={self.exception_symbol!r})"
        )


class RenderableFunction(Renderable):
    # derived from the __str__ code in boolean.py

    def render(self, template="{symbol.key}", *args, **kwargs):
        """
        Render an expression as a string, recursively applying the string
        ``template`` to every symbols and operators.
        """
        expression_args = self.args
        if len(expression_args) == 1:
            # a bare symbol
            sym = expression_args[0]
            if isinstance(sym, Renderable):
                sym = sym.render(template, *args, **kwargs)

            else:
                # FIXME: CAN THIS EVER HAPPEN since we only have symbols OR and AND?
                print(
                    f"WARNING: symbol is not renderable: using plain string representation: {sym!r}"
                )
                sym = str(sym)

            # NB: the operator str already has a leading and trailing space
            if self.isliteral:
                rendered = f"{self.operator}{sym}"
            else:
                rendered = f"{self.operator}({sym})"
            return rendered

        rendered_items = []
        rendered_items_append = rendered_items.append
        for arg in expression_args:
            if isinstance(arg, Renderable):
                # recurse
                rendered = arg.render(template, *args, **kwargs)

            else:
                # FIXME: CAN THIS EVER HAPPEN since we only have symbols OR and AND?
                print(
                    "WARNING: object in expression is not renderable: "
                    f"falling back to plain string representation: {arg!r}."
                )
                rendered = str(arg)

            if arg.isliteral:
                rendered_items_append(rendered)
            else:
                rendered_items_append(f"({rendered})")

        return self.operator.join(rendered_items)


class AND(RenderableFunction, boolean.AND):
    """
    Custom representation for the AND operator to uppercase.
    """

    def __init__(self, *args):
        if len(args) < 2:
            raise ExpressionError("AND requires two or more licenses as in: MIT AND BSD")
        super(AND, self).__init__(*args)
        self.operator = " AND "


class OR(RenderableFunction, boolean.OR):
    """
    Custom representation for the OR operator to uppercase.
    """

    def __init__(self, *args):
        if len(args) < 2:
            raise ExpressionError("OR requires two or more licenses as in: MIT OR BSD")
        super(OR, self).__init__(*args)
        self.operator = " OR "


def ordered_unique(seq):
    """
    Return unique items in a sequence ``seq`` preserving their original order.
    """
    if not seq:
        return []
    uniques = []
    for item in seq:
        if item in uniques:
            continue
        uniques.append(item)
    return uniques


def as_symbols(symbols):
    """
    Return an iterable of LicenseSymbol objects from a ``symbols`` sequence of
    strings or LicenseSymbol-like objects.

    If an item is a string, then create a new LicenseSymbol for it using the
    string as key.
    If this is not a string it must be a LicenseSymbol- like type. Raise a
    TypeError expection if an item is neither a string or LicenseSymbol- like.
    """
    if symbols:
        for symbol in symbols:
            if not symbol:
                continue
            if isinstance(symbol, bytes):
                try:
                    symbol = str(symbol)
                except:
                    raise TypeError(f"{symbol!r} is not a string.")

            if isinstance(symbol, str):
                if symbol.strip():
                    yield LicenseSymbol(symbol)

            elif isinstance(symbol, LicenseSymbol):
                yield symbol

            elif LicenseSymbol.symbol_like(symbol):
                yield LicenseSymbolLike(symbol)

            else:
                raise TypeError(f"{symbol!r} is neither a string nor LicenseSymbol-like.")


def validate_symbols(symbols, validate_keys=False):
    """
    Return a tuple of (`warnings`, `errors`) given a sequence of ``symbols``
    LicenseSymbol-like objects.

    - `warnings` is a list of validation warnings messages (possibly empty if
      there were no warnings).
    - `errors` is a list of validation error messages (possibly empty if there
      were no errors).

    Keys and aliases are cleaned and validated for uniqueness.

    If ``validate_keys`` also validate that license keys are known keys.
    """

    # collection used for checking unicity and correctness
    seen_keys = set()
    seen_aliases = {}
    seen_exceptions = set()

    # collections to accumulate invalid data and build error messages at the end
    not_symbol_classes = []
    dupe_keys = set()
    dupe_exceptions = set()
    dupe_aliases = defaultdict(list)
    invalid_keys_as_kw = set()
    invalid_alias_as_kw = defaultdict(list)

    # warning
    warning_dupe_aliases = set()

    for symbol in symbols:
        if not isinstance(symbol, LicenseSymbol):
            not_symbol_classes.append(symbol)
            continue

        key = symbol.key
        key = key.strip()
        keyl = key.lower()

        # ensure keys are unique
        if keyl in seen_keys:
            dupe_keys.add(key)

        # key cannot be an expression keyword
        if keyl in KEYWORDS_STRINGS:
            invalid_keys_as_kw.add(key)

        # keep a set of unique seen keys
        seen_keys.add(keyl)

        # aliases is an optional attribute
        aliases = getattr(symbol, "aliases", [])
        initial_alias_len = len(aliases)

        # always normalize aliases for spaces and case
        aliases = set([" ".join(alias.lower().strip().split()) for alias in aliases])

        # KEEP UNIQUES, remove empties
        aliases = set(a for a in aliases if a)

        # issue a warning when there are duplicated or empty aliases
        if len(aliases) != initial_alias_len:
            warning_dupe_aliases.add(key)

        # always add a lowercase key as an alias
        aliases.add(keyl)

        for alias in aliases:
            # note that we do not treat as an error the presence of a duplicated
            # alias pointing to the same key

            # ensure that a possibly duplicated alias does not point to another key
            aliased_key = seen_aliases.get(alias)
            if aliased_key and aliased_key != keyl:
                dupe_aliases[alias].append(key)

            # an alias cannot be an expression keyword
            if alias in KEYWORDS_STRINGS:
                invalid_alias_as_kw[key].append(alias)

            seen_aliases[alias] = keyl

        if symbol.is_exception:
            if keyl in seen_exceptions:
                dupe_exceptions.add(keyl)
            else:
                seen_exceptions.add(keyl)

    # build warning and error messages from invalid data
    errors = []
    for ind in sorted(not_symbol_classes):
        errors.append(f"Invalid item: not a LicenseSymbol object: {ind!r}.")

    for dupe in sorted(dupe_keys):
        errors.append(f"Invalid duplicated license key: {dupe!r}.")

    for dalias, dkeys in sorted(dupe_aliases.items()):
        dkeys = ", ".join(dkeys)
        errors.append(
            f"Invalid duplicated alias pointing to multiple keys: "
            f"{dalias} point to keys: {dkeys!r}."
        )

    for ikey, ialiases in sorted(invalid_alias_as_kw.items()):
        ialiases = ", ".join(ialiases)
        errors.append(
            f"Invalid aliases: an alias cannot be an expression keyword. "
            f"key: {ikey!r}, aliases: {ialiases}."
        )

    for dupe in sorted(dupe_exceptions):
        errors.append(f"Invalid duplicated license exception key: {dupe}.")

    for ikw in sorted(invalid_keys_as_kw):
        errors.append(f"Invalid key: a key cannot be an expression keyword: {ikw}.")

    warnings = []
    for dupe_alias in sorted(dupe_aliases):
        errors.append(f"Duplicated or empty aliases ignored for license key: {dupe_alias!r}.")

    return warnings, errors


def combine_expressions(
    expressions,
    relation="AND",
    unique=True,
    licensing=Licensing(),
):
    """
    Return a combined LicenseExpression object with the `relation`, given a list
    of license ``expressions`` strings or LicenseExpression objects. If
    ``unique`` is True remove duplicates before combining expressions.

    For example::
        >>> a = 'mit'
        >>> b = 'gpl'
        >>> str(combine_expressions([a, b]))
        'mit AND gpl'
        >>> assert 'mit' == str(combine_expressions([a]))
        >>> combine_expressions([])
        >>> combine_expressions(None)
        >>> str(combine_expressions(('gpl', 'mit', 'apache',)))
        'gpl AND mit AND apache'
        >>> str(combine_expressions(('gpl', 'mit', 'apache',), relation='OR'))
        'gpl OR mit OR apache'
        >>> str(combine_expressions(('gpl', 'mit', 'mit',)))
        'gpl AND mit'
        >>> str(combine_expressions(('mit WITH foo', 'gpl', 'mit',)))
        'mit WITH foo AND gpl AND mit'
        >>> str(combine_expressions(('gpl', 'mit', 'mit',), relation='OR', unique=False))
        'gpl OR mit OR mit'
        >>> str(combine_expressions(('mit', 'gpl', 'mit',)))
        'mit AND gpl'
    """
    if not expressions:
        return

    if not isinstance(expressions, (list, tuple)):
        raise TypeError(f"expressions should be a list or tuple and not: {type(expressions)}")

    if not relation or relation.upper() not in (
        "AND",
        "OR",
    ):
        raise TypeError(f"relation should be one of AND, OR and not: {relation}")

    # only deal with LicenseExpression objects
    expressions = [licensing.parse(le, simple=True) for le in expressions]

    if unique:
        # Remove duplicate element in the expressions list
        # and preserve original order
        expressions = list({str(x): x for x in expressions}.values())

    if len(expressions) == 1:
        return expressions[0]

    relation = {"AND": licensing.AND, "OR": licensing.OR}[relation]
    return relation(*expressions)
