"""
Boolean Algebra.

This module defines a Boolean Algebra over the set {TRUE, FALSE} with boolean
variables and the boolean functions AND, OR, NOT. For extensive documentation
look either into the docs directory or view it online, at
https://booleanpy.readthedocs.org/en/latest/.

Copyright (c) Sebastian Kraemer, basti.kr@gmail.com and others

SPDX-License-Identifier: BSD-2-Clause
"""

from boolean.boolean import (
    AND,
    NOT,
    OR,
    PARSE_ERRORS,
    TOKEN_AND,
    TOKEN_FALSE,
    TOKEN_LPAR,
    TOKEN_NOT,
    TOKEN_OR,
    TOKEN_RPAR,
    TOKEN_SYMBOL,
    TOKEN_TRUE,
    BooleanAlgebra,
    Expression,
    ParseError,
    Symbol,
)
