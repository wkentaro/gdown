"""
Boolean expressions algebra.

This module defines a Boolean algebra over the set {TRUE, FALSE} with boolean
variables called Symbols and the boolean functions AND, OR, NOT.

Some basic logic comparison is supported: two expressions can be
compared for equivalence or containment. Furthermore you can simplify
an expression and obtain its normal form.

You can create expressions in Python using familiar boolean operators
or parse expressions from strings. The parsing can be extended with
your own tokenizer.  You can also customize how expressions behave and
how they are presented.

For extensive documentation look either into the docs directory or view it
online, at https://booleanpy.readthedocs.org/en/latest/.

Copyright (c) Sebastian Kraemer, basti.kr@gmail.com and others

SPDX-License-Identifier: BSD-2-Clause
"""

import inspect
import itertools
from functools import reduce  # NOQA
from operator import and_ as and_operator
from operator import or_ as or_operator

# Set to True to enable tracing for parsing
TRACE_PARSE = False

# Token types for standard operators and parens
TOKEN_AND = 1
TOKEN_OR = 2
TOKEN_NOT = 3
TOKEN_LPAR = 4
TOKEN_RPAR = 5
TOKEN_TRUE = 6
TOKEN_FALSE = 7
TOKEN_SYMBOL = 8

TOKEN_TYPES = {
    TOKEN_AND: "AND",
    TOKEN_OR: "OR",
    TOKEN_NOT: "NOT",
    TOKEN_LPAR: "(",
    TOKEN_RPAR: ")",
    TOKEN_TRUE: "TRUE",
    TOKEN_FALSE: "FALSE",
    TOKEN_SYMBOL: "SYMBOL",
}

# parsing error code and messages
PARSE_UNKNOWN_TOKEN = 1
PARSE_UNBALANCED_CLOSING_PARENS = 2
PARSE_INVALID_EXPRESSION = 3
PARSE_INVALID_NESTING = 4
PARSE_INVALID_SYMBOL_SEQUENCE = 5
PARSE_INVALID_OPERATOR_SEQUENCE = 6

PARSE_ERRORS = {
    PARSE_UNKNOWN_TOKEN: "Unknown token",
    PARSE_UNBALANCED_CLOSING_PARENS: "Unbalanced parenthesis",
    PARSE_INVALID_EXPRESSION: "Invalid expression",
    PARSE_INVALID_NESTING: "Invalid expression nesting such as (AND xx)",
    PARSE_INVALID_SYMBOL_SEQUENCE: "Invalid symbols sequence such as (A B)",
    PARSE_INVALID_OPERATOR_SEQUENCE: "Invalid operator sequence without symbols such as AND OR or OR OR",
}


class ParseError(Exception):
    """
    Raised when the parser or tokenizer encounters a syntax error. Instances of
    this class have attributes token_type, token_string, position, error_code to
    access the details of the error. str() of the exception instance returns a
    formatted message.
    """

    def __init__(self, token_type=None, token_string="", position=-1, error_code=0):
        self.token_type = token_type
        self.token_string = token_string
        self.position = position
        self.error_code = error_code

    def __str__(self, *args, **kwargs):
        emsg = PARSE_ERRORS.get(self.error_code, "Unknown parsing error")

        tstr = ""
        if self.token_string:
            tstr = f' for token: "{self.token_string}"'

        pos = ""
        if self.position > 0:
            pos = f" at position: {self.position}"

        return f"{emsg}{tstr}{pos}"


class BooleanAlgebra(object):
    """
    An algebra is defined by:

    - the types of its operations and Symbol.
    - the tokenizer used when parsing expressions from strings.

    This class also serves as a base class for all boolean expressions,
    including base elements, functions and variable symbols.
    """

    def __init__(
        self,
        TRUE_class=None,
        FALSE_class=None,
        Symbol_class=None,
        NOT_class=None,
        AND_class=None,
        OR_class=None,
        allowed_in_token=(".", ":", "_"),
    ):
        """
        The types for TRUE, FALSE, NOT, AND, OR and Symbol define the boolean
        algebra elements, operations and Symbol variable. They default to the
        standard classes if not provided.

        You can customize an algebra by providing alternative subclasses of the
        standard types.
        """
        # TRUE and FALSE base elements are algebra-level "singleton" instances
        self.TRUE = TRUE_class or _TRUE
        self.TRUE = self.TRUE()

        self.FALSE = FALSE_class or _FALSE
        self.FALSE = self.FALSE()

        # they cross-reference each other
        self.TRUE.dual = self.FALSE
        self.FALSE.dual = self.TRUE

        # boolean operation types, defaulting to the standard types
        self.NOT = NOT_class or NOT
        self.AND = AND_class or AND
        self.OR = OR_class or OR

        # class used for Symbols
        self.Symbol = Symbol_class or Symbol

        tf_nao = {
            "TRUE": self.TRUE,
            "FALSE": self.FALSE,
            "NOT": self.NOT,
            "AND": self.AND,
            "OR": self.OR,
            "Symbol": self.Symbol,
        }

        # setup cross references such that all algebra types and
        # objects hold a named attribute for every other types and
        # objects, including themselves.
        for obj in tf_nao.values():
            for name, value in tf_nao.items():
                setattr(obj, name, value)

        # Set the set of characters allowed in tokens
        self.allowed_in_token = allowed_in_token

    def definition(self):
        """
        Return a tuple of this algebra defined elements and types as:
        (TRUE, FALSE, NOT, AND, OR, Symbol)
        """
        return self.TRUE, self.FALSE, self.NOT, self.AND, self.OR, self.Symbol

    def symbols(self, *args):
        """
        Return a tuple of symbols building a new Symbol from each argument.
        """
        return tuple(map(self.Symbol, args))

    def parse(self, expr, simplify=False):
        """
        Return a boolean expression parsed from `expr` either a unicode string
        or tokens iterable.

        Optionally simplify the expression if `simplify` is True.

        Raise ParseError on errors.

        If `expr` is a string, the standard `tokenizer` is used for tokenization
        and the algebra configured Symbol type is used to create Symbol
        instances from Symbol tokens.

        If `expr` is an iterable, it should contain 3-tuples of: (token_type,
        token_string, token_position). In this case, the `token_type` can be
        a Symbol instance or one of the TOKEN_* constant types.
        See the `tokenize()` method for detailed specification.
        """

        precedence = {self.NOT: 5, self.AND: 10, self.OR: 15, TOKEN_LPAR: 20}

        if isinstance(expr, str):
            tokenized = self.tokenize(expr)
        else:
            tokenized = iter(expr)

        if TRACE_PARSE:
            tokenized = list(tokenized)
            print("tokens:")
            for t in tokenized:
                print(t)
            tokenized = iter(tokenized)

        # the abstract syntax tree for this expression that will be build as we
        # process tokens
        # the first two items are None
        # symbol items are appended to this structure
        ast = [None, None]

        def is_sym(_t):
            return isinstance(_t, Symbol) or _t in (TOKEN_TRUE, TOKEN_FALSE, TOKEN_SYMBOL)

        def is_operator(_t):
            return _t in (TOKEN_AND, TOKEN_OR)

        prev_token = None
        for token_type, token_string, token_position in tokenized:
            if TRACE_PARSE:
                print(
                    "\nprocessing token_type:",
                    repr(token_type),
                    "token_string:",
                    repr(token_string),
                    "token_position:",
                    repr(token_position),
                )

            if prev_token:
                prev_token_type, _prev_token_string, _prev_token_position = prev_token
                if TRACE_PARSE:
                    print("  prev_token:", repr(prev_token))

                if is_sym(prev_token_type) and (
                    is_sym(token_type)
                ):  # or token_type == TOKEN_LPAR) :
                    raise ParseError(
                        token_type, token_string, token_position, PARSE_INVALID_SYMBOL_SEQUENCE
                    )

                if is_operator(prev_token_type) and (
                    is_operator(token_type) or token_type == TOKEN_RPAR
                ):
                    raise ParseError(
                        token_type, token_string, token_position, PARSE_INVALID_OPERATOR_SEQUENCE
                    )

            else:
                if is_operator(token_type):
                    raise ParseError(
                        token_type, token_string, token_position, PARSE_INVALID_OPERATOR_SEQUENCE
                    )

            if token_type == TOKEN_SYMBOL:
                ast.append(self.Symbol(token_string))
                if TRACE_PARSE:
                    print(" ast: token_type is TOKEN_SYMBOL: append new symbol", repr(ast))

            elif isinstance(token_type, Symbol):
                ast.append(token_type)
                if TRACE_PARSE:
                    print(" ast: token_type is Symbol): append existing symbol", repr(ast))

            elif token_type == TOKEN_TRUE:
                ast.append(self.TRUE)
                if TRACE_PARSE:
                    print(" ast: token_type is TOKEN_TRUE:", repr(ast))

            elif token_type == TOKEN_FALSE:
                ast.append(self.FALSE)
                if TRACE_PARSE:
                    print(" ast: token_type is TOKEN_FALSE:", repr(ast))

            elif token_type == TOKEN_NOT:
                ast = [ast, self.NOT]
                if TRACE_PARSE:
                    print(" ast: token_type is TOKEN_NOT:", repr(ast))

            elif token_type == TOKEN_AND:
                ast = self._start_operation(ast, self.AND, precedence)
                if TRACE_PARSE:
                    print("  ast:token_type is TOKEN_AND: start_operation", ast)

            elif token_type == TOKEN_OR:
                ast = self._start_operation(ast, self.OR, precedence)
                if TRACE_PARSE:
                    print("  ast:token_type is TOKEN_OR: start_operation", ast)

            elif token_type == TOKEN_LPAR:
                if prev_token:
                    # Check that an opening parens is preceded by a function
                    # or an opening parens
                    if prev_token_type not in (TOKEN_NOT, TOKEN_AND, TOKEN_OR, TOKEN_LPAR):
                        raise ParseError(
                            token_type, token_string, token_position, PARSE_INVALID_NESTING
                        )
                ast = [ast, TOKEN_LPAR]

            elif token_type == TOKEN_RPAR:
                while True:
                    if ast[0] is None:
                        raise ParseError(
                            token_type,
                            token_string,
                            token_position,
                            PARSE_UNBALANCED_CLOSING_PARENS,
                        )

                    if ast[1] is TOKEN_LPAR:
                        ast[0].append(ast[2])
                        if TRACE_PARSE:
                            print("ast9:", repr(ast))
                        ast = ast[0]
                        if TRACE_PARSE:
                            print("ast10:", repr(ast))
                        break

                    if isinstance(ast[1], int):
                        raise ParseError(
                            token_type,
                            token_string,
                            token_position,
                            PARSE_UNBALANCED_CLOSING_PARENS,
                        )

                    # the parens are properly nested
                    # the top ast node should be a function subclass
                    if not (inspect.isclass(ast[1]) and issubclass(ast[1], Function)):
                        raise ParseError(
                            token_type, token_string, token_position, PARSE_INVALID_NESTING
                        )

                    subex = ast[1](*ast[2:])
                    ast[0].append(subex)
                    if TRACE_PARSE:
                        print("ast11:", repr(ast))
                    ast = ast[0]
                    if TRACE_PARSE:
                        print("ast12:", repr(ast))
            else:
                raise ParseError(token_type, token_string, token_position, PARSE_UNKNOWN_TOKEN)

            prev_token = (token_type, token_string, token_position)

        try:
            while True:
                if ast[0] is None:
                    if TRACE_PARSE:
                        print("ast[0] is None:", repr(ast))
                    if ast[1] is None:
                        if TRACE_PARSE:
                            print("  ast[1] is None:", repr(ast))
                        if len(ast) != 3:
                            raise ParseError(error_code=PARSE_INVALID_EXPRESSION)
                        parsed = ast[2]
                        if TRACE_PARSE:
                            print("    parsed = ast[2]:", repr(parsed))

                    else:
                        # call the function in ast[1] with the rest of the ast as args
                        parsed = ast[1](*ast[2:])
                        if TRACE_PARSE:
                            print("  parsed = ast[1](*ast[2:]):", repr(parsed))
                    break
                else:
                    if TRACE_PARSE:
                        print("subex = ast[1](*ast[2:]):", repr(ast))
                    subex = ast[1](*ast[2:])
                    ast[0].append(subex)
                    if TRACE_PARSE:
                        print("  ast[0].append(subex):", repr(ast))
                    ast = ast[0]
                    if TRACE_PARSE:
                        print("    ast = ast[0]:", repr(ast))
        except TypeError:
            raise ParseError(error_code=PARSE_INVALID_EXPRESSION)

        if simplify:
            return parsed.simplify()

        if TRACE_PARSE:
            print("final parsed:", repr(parsed))
        return parsed

    def _start_operation(self, ast, operation, precedence):
        """
        Return an AST where all operations of lower precedence are finalized.
        """
        if TRACE_PARSE:
            print("   start_operation:", repr(operation), "AST:", ast)

        op_prec = precedence[operation]
        while True:
            if ast[1] is None:
                # [None, None, x]
                if TRACE_PARSE:
                    print("     start_op: ast[1] is None:", repr(ast))
                ast[1] = operation
                if TRACE_PARSE:
                    print("     --> start_op: ast[1] is None:", repr(ast))
                return ast

            prec = precedence[ast[1]]
            if prec > op_prec:  # op=&, [ast, |, x, y] -> [[ast, |, x], &, y]
                if TRACE_PARSE:
                    print("     start_op: prec > op_prec:", repr(ast))
                ast = [ast, operation, ast.pop(-1)]
                if TRACE_PARSE:
                    print("     --> start_op: prec > op_prec:", repr(ast))
                return ast

            if prec == op_prec:  # op=&, [ast, &, x] -> [ast, &, x]
                if TRACE_PARSE:
                    print("     start_op: prec == op_prec:", repr(ast))
                return ast

            if not (inspect.isclass(ast[1]) and issubclass(ast[1], Function)):
                # the top ast node should be a function subclass at this stage
                raise ParseError(error_code=PARSE_INVALID_NESTING)

            if ast[0] is None:  # op=|, [None, &, x, y] -> [None, |, x&y]
                if TRACE_PARSE:
                    print("     start_op: ast[0] is None:", repr(ast))
                subexp = ast[1](*ast[2:])
                new_ast = [ast[0], operation, subexp]
                if TRACE_PARSE:
                    print("     --> start_op: ast[0] is None:", repr(new_ast))
                return new_ast

            else:  # op=|, [[ast, &, x], ~, y] -> [ast, &, x, ~y]
                if TRACE_PARSE:
                    print("     start_op: else:", repr(ast))
                ast[0].append(ast[1](*ast[2:]))
                ast = ast[0]
                if TRACE_PARSE:
                    print("     --> start_op: else:", repr(ast))

    def tokenize(self, expr):
        """
        Return an iterable of 3-tuple describing each token given an expression
        unicode string.

        This 3-tuple contains (token, token string, position):

        - token: either a Symbol instance or one of TOKEN_* token types.
        - token string: the original token unicode string.
        - position: some simple object describing the starting position of the
          original token string in the `expr` string. It can be an int for a
          character offset, or a tuple of starting (row/line, column).

        The token position is used only for error reporting and can be None or
        empty.

        Raise ParseError on errors. The ParseError.args is a tuple of:
        (token_string, position, error message)

        You can use this tokenizer as a base to create specialized tokenizers
        for your custom algebra by subclassing BooleanAlgebra. See also the
        tests for other examples of alternative tokenizers.

        This tokenizer has these characteristics:

        - The `expr` string can span multiple lines,
        - Whitespace is not significant.
        - The returned position is the starting character offset of a token.
        - A TOKEN_SYMBOL is returned for valid identifiers which is a string
          without spaces.

            - These are valid identifiers:
                - Python identifiers.
                - a string even if starting with digits
                - digits (except for 0 and 1).
                - dotted names : foo.bar consist of one token.
                - names with colons: foo:bar consist of one token.
            
            - These are not identifiers:
                - quoted strings.
                - any punctuation which is not an operation

        - Recognized operators are (in any upper/lower case combinations):

            - for and:  '*', '&', 'and'
            - for or: '+', '|', 'or'
            - for not: '~', '!', 'not'

        - Recognized special symbols are (in any upper/lower case combinations):

            - True symbols: 1 and True
            - False symbols: 0, False and None
        """
        if not isinstance(expr, str):
            raise TypeError(f"expr must be string but it is {type(expr)}.")

        # mapping of lowercase token strings to a token type id for the standard
        # operators, parens and common true or false symbols, as used in the
        # default tokenizer implementation.
        TOKENS = {
            "*": TOKEN_AND,
            "&": TOKEN_AND,
            "and": TOKEN_AND,
            "+": TOKEN_OR,
            "|": TOKEN_OR,
            "or": TOKEN_OR,
            "~": TOKEN_NOT,
            "!": TOKEN_NOT,
            "not": TOKEN_NOT,
            "(": TOKEN_LPAR,
            ")": TOKEN_RPAR,
            "[": TOKEN_LPAR,
            "]": TOKEN_RPAR,
            "true": TOKEN_TRUE,
            "1": TOKEN_TRUE,
            "false": TOKEN_FALSE,
            "0": TOKEN_FALSE,
            "none": TOKEN_FALSE,
        }

        position = 0
        length = len(expr)

        while position < length:
            tok = expr[position]

            sym = tok.isalnum() or tok == "_"
            if sym:
                position += 1
                while position < length:
                    char = expr[position]
                    if char.isalnum() or char in self.allowed_in_token:
                        position += 1
                        tok += char
                    else:
                        break
                position -= 1

            try:
                yield TOKENS[tok.lower()], tok, position
            except KeyError:
                if sym:
                    yield TOKEN_SYMBOL, tok, position
                elif tok not in (" ", "\t", "\r", "\n"):
                    raise ParseError(
                        token_string=tok, position=position, error_code=PARSE_UNKNOWN_TOKEN
                    )

            position += 1

    def _recurse_distributive(self, expr, operation_inst):
        """
        Recursively flatten, simplify and apply the distributive laws to the
        `expr` expression. Distributivity is considered for the AND or OR
        `operation_inst` instance.
        """
        if expr.isliteral:
            return expr

        args = (self._recurse_distributive(arg, operation_inst) for arg in expr.args)
        args = tuple(arg.simplify() for arg in args)
        if len(args) == 1:
            return args[0]

        flattened_expr = expr.__class__(*args)

        dualoperation = operation_inst.dual
        if isinstance(flattened_expr, dualoperation):
            flattened_expr = flattened_expr.distributive()
        return flattened_expr

    def normalize(self, expr, operation):
        """
        Return a normalized expression transformed to its normal form in the
        given AND or OR operation.

        The new expression arguments will satisfy these conditions:
    
        - ``operation(*args) == expr`` (here mathematical equality is meant)
        - the operation does not occur in any of its arg.
        - NOT is only appearing in literals (aka. Negation normal form).

        The operation must be an AND or OR operation or a subclass.
        """
        # Ensure that the operation is not NOT
        assert operation in (
            self.AND,
            self.OR,
        )
        # Move NOT inwards.
        expr = expr.literalize()
        # Simplify first otherwise _recurse_distributive() may take forever.
        expr = expr.simplify()
        operation_example = operation(self.TRUE, self.FALSE)

        # For large dual operations build up from normalized subexpressions,
        # otherwise we can get exponential blowup midway through
        expr.args = tuple(self.normalize(a, operation) for a in expr.args)
        if len(expr.args) > 1 and (
            (operation == self.AND and isinstance(expr, self.OR))
            or (operation == self.OR and isinstance(expr, self.AND))
        ):
            args = expr.args
            expr_class = expr.__class__
            expr = args[0]
            for arg in args[1:]:
                expr = expr_class(expr, arg)
                expr = self._recurse_distributive(expr, operation_example)
                # Canonicalize
                expr = expr.simplify()

        else:
            expr = self._recurse_distributive(expr, operation_example)
            # Canonicalize
            expr = expr.simplify()

        return expr

    def cnf(self, expr):
        """
        Return a conjunctive normal form of the `expr` expression.
        """
        return self.normalize(expr, self.AND)

    conjunctive_normal_form = cnf

    def dnf(self, expr):
        """
        Return a disjunctive normal form of the `expr` expression.
        """
        return self.normalize(expr, self.OR)

    disjunctive_normal_form = dnf


class Expression(object):
    """
    Abstract base class for all boolean expressions, including functions and
    variable symbols.
    """

    # these class attributes are configured when a new BooleanAlgebra is created
    TRUE = None
    FALSE = None
    NOT = None
    AND = None
    OR = None
    Symbol = None

    def __init__(self):
        # Defines sort and comparison order between expressions arguments
        self.sort_order = None

        # Store arguments aka. subterms of this expressions.
        # subterms are either literals or expressions.
        self.args = tuple()

        # True is this is a literal expression such as a Symbol, TRUE or FALSE
        self.isliteral = False

        # True if this expression has been simplified to in canonical form.
        self.iscanonical = False

    @property
    def objects(self):
        """
        Return a set of all associated objects with this expression symbols.
        Include recursively subexpressions objects.
        """
        return set(s.obj for s in self.symbols)

    def get_literals(self):
        """
        Return a list of all the literals contained in this expression.
        Include recursively subexpressions symbols.
        This includes duplicates.
        """
        if self.isliteral:
            return [self]
        if not self.args:
            return []
        return list(itertools.chain.from_iterable(arg.get_literals() for arg in self.args))

    @property
    def literals(self):
        """
        Return a set of all literals contained in this expression.
        Include recursively subexpressions literals.
        """
        return set(self.get_literals())

    def literalize(self):
        """
        Return an expression where NOTs are only occurring as literals.
        Applied recursively to subexpressions.
        """
        if self.isliteral:
            return self
        args = tuple(arg.literalize() for arg in self.args)
        if all(arg is self.args[i] for i, arg in enumerate(args)):
            return self

        return self.__class__(*args)

    def get_symbols(self):
        """
        Return a list of all the symbols contained in this expression.
        Include subexpressions symbols recursively.
        This includes duplicates.
        """
        return [s if isinstance(s, Symbol) else s.args[0] for s in self.get_literals()]

    @property
    def symbols(
        self,
    ):
        """
        Return a list of all the symbols contained in this expression.
        Include subexpressions symbols recursively.
        This includes duplicates.
        """
        return set(self.get_symbols())

    def subs(self, substitutions, default=None, simplify=False):
        """
        Return an expression where all subterms of this expression are
        by the new expression using a `substitutions` mapping of:
        {expr: replacement}

        Return the provided `default` value if this expression has no elements,
        e.g. is empty.

        Simplify the results if `simplify` is True.

        Return this expression unmodified if nothing could be substituted. Note
        that a possible usage of this function is to check for expression
        containment as the expression will be returned unmodified if if does not
        contain any of the provided substitutions.
        """
        # shortcut: check if we have our whole expression as a possible
        # subsitution source
        for expr, substitution in substitutions.items():
            if expr == self:
                return substitution

        # otherwise, do a proper substitution of subexpressions
        expr = self._subs(substitutions, default, simplify)
        return self if expr is None else expr

    def _subs(self, substitutions, default, simplify):
        """
        Return an expression where all subterms are substituted by the new
        expression using a `substitutions` mapping of: {expr: replacement}
        """
        # track the new list of unchanged args or replaced args through
        # a substitution
        new_arguments = []
        changed_something = False

        # shortcut for basic logic True or False
        if self is self.TRUE or self is self.FALSE:
            return self

        # if the expression has no elements, e.g. is empty, do not apply
        # substitutions
        if not self.args:
            return default

        # iterate the subexpressions: either plain symbols or a subexpressions
        for arg in self.args:
            # collect substitutions for exact matches
            # break as soon as we have a match
            for expr, substitution in substitutions.items():
                if arg == expr:
                    new_arguments.append(substitution)
                    changed_something = True
                    break

            # this will execute only if we did not break out of the
            # loop, e.g. if we did not change anything and did not
            # collect any substitutions
            else:
                # recursively call _subs on each arg to see if we get a
                # substituted arg
                new_arg = arg._subs(substitutions, default, simplify)
                if new_arg is None:
                    # if we did not collect a substitution for this arg,
                    # keep the arg as-is, it is not replaced by anything
                    new_arguments.append(arg)
                else:
                    # otherwise, we add the substitution for this arg instead
                    new_arguments.append(new_arg)
                    changed_something = True

        if not changed_something:
            return

        # here we did some substitution: we return a new expression
        # built from the new_arguments
        newexpr = self.__class__(*new_arguments)
        return newexpr.simplify() if simplify else newexpr

    def simplify(self):
        """
        Return a new simplified expression in canonical form built from this
        expression. The simplified expression may be exactly the same as this
        expression.

        Subclasses override this method to compute actual simplification.
        """
        return self

    def __hash__(self):
        """
        Expressions are immutable and hashable. The hash of Functions is
        computed by respecting the structure of the whole expression by mixing
        the class name hash and the recursive hash of a frozenset of arguments.
        Hash of elements is based on their boolean equivalent. Hash of symbols
        is based on their object.
        """
        if not self.args:
            arghash = id(self)
        else:
            arghash = hash(frozenset(map(hash, self.args)))
        return hash(self.__class__.__name__) ^ arghash

    def __eq__(self, other):
        """
        Test if other element is structurally the same as itself.

        This method does not make any simplification or transformation, so it
        will return False although the expression terms may be mathematically
        equal. Use simplify() before testing equality to check the mathematical
        equality.

        For literals, plain equality is used.

        For functions, equality uses the facts that operations are:

        - commutative: order does not matter and different orders are equal.
        - idempotent: so args can appear more often in one term than in the other.
        """
        if self is other:
            return True

        if isinstance(other, self.__class__):
            return frozenset(self.args) == frozenset(other.args)

        return NotImplemented

    def __ne__(self, other):
        return not self == other

    def __lt__(self, other):
        if self.sort_order is not None and other.sort_order is not None:
            if self.sort_order == other.sort_order:
                return NotImplemented
            return self.sort_order < other.sort_order
        return NotImplemented

    def __gt__(self, other):
        lt = other.__lt__(self)
        if lt is NotImplemented:
            self_lt = self.__lt__(other)
            if self_lt is NotImplemented:
                # `return not NotImplemented`` no longer works in Python 3.14
                return False
            else:
                return not self_lt
        return lt

    def __and__(self, other):
        return self.AND(self, other)

    __mul__ = __and__

    def __invert__(self):
        return self.NOT(self)

    def __or__(self, other):
        return self.OR(self, other)

    __add__ = __or__

    def __bool__(self):
        raise TypeError("Cannot evaluate expression as a Python Boolean.")

    __nonzero__ = __bool__


class BaseElement(Expression):
    """
    Abstract base class for the base elements TRUE and FALSE of the boolean
    algebra.
    """

    def __init__(self):
        super(BaseElement, self).__init__()
        self.sort_order = 0
        self.iscanonical = True
        # The dual Base Element class for this element: TRUE.dual returns
        # _FALSE() and FALSE.dual returns _TRUE(). This is a cyclic reference
        # and therefore only assigned after creation of the singletons,
        self.dual = None

    def __lt__(self, other):
        if isinstance(other, BaseElement):
            return self == self.FALSE
        return NotImplemented

    __nonzero__ = __bool__ = lambda s: None

    def pretty(self, indent=0, debug=False):
        """
        Return a pretty formatted representation of self.
        """
        return (" " * indent) + repr(self)


class _TRUE(BaseElement):
    """
    Boolean base element TRUE.
    Not meant to be subclassed nor instantiated directly.
    """

    def __init__(self):
        super(_TRUE, self).__init__()
        # assigned at singleton creation: self.dual = FALSE

    def __hash__(self):
        return hash(True)

    def __eq__(self, other):
        return self is other or other is True or isinstance(other, _TRUE)

    def __str__(self):
        return "1"

    def __repr__(self):
        return "TRUE"

    def __call__(self):
        return self

    __nonzero__ = __bool__ = lambda s: True


class _FALSE(BaseElement):
    """
    Boolean base element FALSE.
    Not meant to be subclassed nor instantiated directly.
    """

    def __init__(self):
        super(_FALSE, self).__init__()
        # assigned at singleton creation: self.dual = TRUE

    def __hash__(self):
        return hash(False)

    def __eq__(self, other):
        return self is other or other is False or isinstance(other, _FALSE)

    def __str__(self):
        return "0"

    def __repr__(self):
        return "FALSE"

    def __call__(self):
        return self

    __nonzero__ = __bool__ = lambda s: False


class Symbol(Expression):
    """
    Boolean variable.

    A Symbol can hold an object used to determine equality between symbols.
    """

    def __init__(self, obj):
        super(Symbol, self).__init__()
        self.sort_order = 5
        # Store an associated object. This object determines equality
        self.obj = obj
        self.iscanonical = True
        self.isliteral = True

    def __call__(self, **kwargs):
        """
        Return the evaluated value for this symbol from kwargs
        """
        return kwargs[self.obj]

    def __hash__(self):
        if self.obj is None:  # Anonymous Symbol.
            return id(self)
        return hash(self.obj)

    def __eq__(self, other):
        if self is other:
            return True
        if isinstance(other, self.__class__):
            return self.obj == other.obj
        return NotImplemented

    def __lt__(self, other):
        comparator = Expression.__lt__(self, other)
        if comparator is not NotImplemented:
            return comparator
        if isinstance(other, Symbol):
            return self.obj < other.obj
        return NotImplemented

    def __str__(self):
        return str(self.obj)

    def __repr__(self):
        obj = f"'{self.obj}'" if isinstance(self.obj, str) else repr(self.obj)
        return f"{self.__class__.__name__}({obj})"

    def pretty(self, indent=0, debug=False):
        """
        Return a pretty formatted representation of self.
        """
        debug_details = ""
        if debug:
            debug_details += f"<isliteral={self.isliteral!r}, iscanonical={self.iscanonical!r}>"

        obj = f"'{self.obj}'" if isinstance(self.obj, str) else repr(self.obj)
        return (" " * indent) + f"{self.__class__.__name__}({debug_details}{obj})"


class Function(Expression):
    """
    Boolean function.

    A boolean function takes n (one or more) boolean expressions as arguments
    where n is called the order of the function and maps them to one of the base
    elements TRUE or FALSE. Implemented functions are AND, OR and NOT.
    """

    def __init__(self, *args):
        super(Function, self).__init__()

        # Specifies an infix notation of an operator for printing such as | or &.
        self.operator = None

        assert all(
            isinstance(arg, Expression) for arg in args
        ), f"Bad arguments: all arguments must be an Expression: {args!r}"
        self.args = tuple(args)

    def __str__(self):
        args = self.args
        if len(args) == 1:
            if self.isliteral:
                return f"{self.operator}{args[0]}"
            return f"{self.operator}({args[0]})"

        args_str = []
        for arg in args:
            if arg.isliteral:
                args_str.append(str(arg))
            else:
                args_str.append(f"({arg})")

        return self.operator.join(args_str)

    def __repr__(self):
        args = ", ".join(map(repr, self.args))
        return f"{self.__class__.__name__}({args})"

    def pretty(self, indent=0, debug=False):
        """
        Return a pretty formatted representation of self as an indented tree.

        If debug is True, also prints debug information for each expression arg.

        For example:

        >>> print(BooleanAlgebra().parse(
        ...    u'not a and not b and not (a and ba and c) and c or c').pretty())
        OR(
          AND(
            NOT(Symbol('a')),
            NOT(Symbol('b')),
            NOT(
              AND(
                Symbol('a'),
                Symbol('ba'),
                Symbol('c')
              )
            ),
            Symbol('c')
          ),
          Symbol('c')
        )
        """
        debug_details = ""
        if debug:
            debug_details += f"<isliteral={self.isliteral!r}, iscanonical={self.iscanonical!r}"
            identity = getattr(self, "identity", None)
            if identity is not None:
                debug_details += f", identity={identity!r}"

            annihilator = getattr(self, "annihilator", None)
            if annihilator is not None:
                debug_details += f", annihilator={annihilator!r}"

            dual = getattr(self, "dual", None)
            if dual is not None:
                debug_details += f", dual={dual!r}"
            debug_details += ">"
        cls = self.__class__.__name__
        args = [a.pretty(indent=indent + 2, debug=debug) for a in self.args]
        pfargs = ",\n".join(args)
        cur_indent = " " * indent
        new_line = "" if self.isliteral else "\n"
        return f"{cur_indent}{cls}({debug_details}{new_line}{pfargs}\n{cur_indent})"


class NOT(Function):
    """
    Boolean NOT operation.

    The NOT operation takes exactly one argument. If this argument is a Symbol
    the resulting expression is also called a literal.

    The operator "~" can be used as abbreviation for NOT, e.g. instead of NOT(x)
    one can write ~x (where x is some boolean expression). Also for printing "~"
    is used for better readability.

    You can subclass to define alternative string representation.

    For example:

    >>> class NOT2(NOT):
    ...     def __init__(self, *args):
    ...         super(NOT2, self).__init__(*args)
    ...         self.operator = '!'
    """

    def __init__(self, arg1):
        super(NOT, self).__init__(arg1)
        self.isliteral = isinstance(self.args[0], Symbol)
        self.operator = "~"

    def literalize(self):
        """
        Return an expression where NOTs are only occurring as literals.
        """
        expr = self.demorgan()
        if isinstance(expr, self.__class__):
            return expr
        return expr.literalize()

    def simplify(self):
        """
        Return a simplified expr in canonical form.

        This means double negations are canceled out and all contained boolean
        objects are in their canonical form.
        """
        if self.iscanonical:
            return self

        expr = self.cancel()
        if not isinstance(expr, self.__class__):
            return expr.simplify()

        if expr.args[0] in (
            self.TRUE,
            self.FALSE,
        ):
            return expr.args[0].dual

        expr = self.__class__(expr.args[0].simplify())
        expr.iscanonical = True
        return expr

    def cancel(self):
        """
        Cancel itself and following NOTs as far as possible.
        Returns the simplified expression.
        """
        expr = self
        while True:
            arg = expr.args[0]
            if not isinstance(arg, self.__class__):
                return expr
            expr = arg.args[0]
            if not isinstance(expr, self.__class__):
                return expr

    def demorgan(self):
        """
        Return a expr where the NOT function is moved inward.
        This is achieved by canceling double NOTs and using De Morgan laws.
        """
        expr = self.cancel()
        if expr.isliteral or not isinstance(expr, self.NOT):
            return expr
        op = expr.args[0]
        return op.dual(*(self.__class__(arg).cancel() for arg in op.args))

    def __call__(self, **kwargs):
        """
        Return the evaluated (negated) value for this function.
        """
        return not self.args[0](**kwargs)

    def __lt__(self, other):
        return self.args[0] < other

    def pretty(self, indent=1, debug=False):
        """
        Return a pretty formatted representation of self.
        Include additional debug details if `debug` is True.
        """
        debug_details = ""
        if debug:
            debug_details += f"<isliteral={self.isliteral!r}, iscanonical={self.iscanonical!r}>"
        if self.isliteral:
            pretty_literal = self.args[0].pretty(indent=0, debug=debug)
            return (" " * indent) + f"{self.__class__.__name__}({debug_details}{pretty_literal})"
        else:
            return super(NOT, self).pretty(indent=indent, debug=debug)


class DualBase(Function):
    """
    Base class for AND and OR function.

    This class uses the duality principle to combine similar methods of AND
    and OR. Both operations take two or more arguments and can be created using
    "|" for OR and "&" for AND.
    """

    _pyoperator = None

    def __init__(self, arg1, arg2, *args):
        super(DualBase, self).__init__(arg1, arg2, *args)

        # identity element for the specific operation.
        # This will be TRUE for the AND operation and FALSE for the OR operation.
        self.identity = None

        # annihilator element for this function.
        # This will be FALSE for the AND operation and TRUE for the OR operation.
        self.annihilator = None

        # dual class of this function.
        # This means OR.dual returns AND and AND.dual returns OR.
        self.dual = None

    def __contains__(self, expr):
        """
        Test if expr is a subterm of this expression.
        """
        if expr in self.args:
            return True

        if isinstance(expr, self.__class__):
            return all(arg in self.args for arg in expr.args)

    def simplify(self, sort=True):
        """
        Return a new simplified expression in canonical form from this
        expression.

        For simplification of AND and OR fthe ollowing rules are used
        recursively bottom up:

        - Associativity (output does not contain same operations nested)::

            (A & B) & C = A & (B & C) = A & B & C
            (A | B) | C = A | (B | C) = A | B | C
         
         
        - Annihilation::

            A & 0 = 0, A | 1 = 1

        - Idempotence (e.g. removing duplicates)::

            A & A = A, A | A = A

        - Identity::

            A & 1 = A, A | 0 = A

        - Complementation::

            A & ~A = 0, A | ~A = 1

        - Elimination::

            (A & B) | (A & ~B) = A, (A | B) & (A | ~B) = A

        - Absorption::

            A & (A | B) = A, A | (A & B) = A

        - Negative absorption::

            A & (~A | B) = A & B, A | (~A & B) = A | B

        - Commutativity (output is always sorted)::

            A & B = B & A, A | B = B | A

        Other boolean objects are also in their canonical form.
        """
        # TODO: Refactor DualBase.simplify into different "sub-evals".

        # If self is already canonical do nothing.
        if self.iscanonical:
            return self

        # Otherwise bring arguments into canonical form.
        args = [arg.simplify() for arg in self.args]

        # Create new instance of own class with canonical args.
        # TODO: Only create new class if some args changed.
        expr = self.__class__(*args)

        # Literalize before doing anything, this also applies De Morgan's Law
        expr = expr.literalize()

        # Associativity:
        #     (A & B) & C = A & (B & C) = A & B & C
        #     (A | B) | C = A | (B | C) = A | B | C
        expr = expr.flatten()

        # Annihilation: A & 0 = 0, A | 1 = 1
        if self.annihilator in expr.args:
            return self.annihilator

        # Idempotence: A & A = A, A | A = A
        # this boils down to removing duplicates
        args = []
        for arg in expr.args:
            if arg not in args:
                args.append(arg)
        if len(args) == 1:
            return args[0]

        # Identity: A & 1 = A, A | 0 = A
        if self.identity in args:
            args.remove(self.identity)
            if len(args) == 1:
                return args[0]

        # Complementation: A & ~A = 0, A | ~A = 1
        for arg in args:
            if self.NOT(arg) in args:
                return self.annihilator

        # Elimination: (A & B) | (A & ~B) = A, (A | B) & (A | ~B) = A
        i = 0
        while i < len(args) - 1:
            j = i + 1
            ai = args[i]
            if not isinstance(ai, self.dual):
                i += 1
                continue
            while j < len(args):
                aj = args[j]
                if not isinstance(aj, self.dual) or len(ai.args) != len(aj.args):
                    j += 1
                    continue

                # Find terms where only one arg is different.
                negated = None
                for arg in ai.args:
                    # FIXME: what does this pass Do?
                    if arg in aj.args:
                        pass
                    elif self.NOT(arg).cancel() in aj.args:
                        if negated is None:
                            negated = arg
                        else:
                            negated = None
                            break
                    else:
                        negated = None
                        break

                # If the different arg is a negation simplify the expr.
                if negated is not None:
                    # Cancel out one of the two terms.
                    del args[j]
                    aiargs = list(ai.args)
                    aiargs.remove(negated)
                    if len(aiargs) == 1:
                        args[i] = aiargs[0]
                    else:
                        args[i] = self.dual(*aiargs)

                    if len(args) == 1:
                        return args[0]
                    else:
                        # Now the other simplifications have to be redone.
                        return self.__class__(*args).simplify()
                j += 1
            i += 1

        # Absorption: A & (A | B) = A, A | (A & B) = A
        # Negative absorption: A & (~A | B) = A & B, A | (~A & B) = A | B
        args = self.absorb(args)
        if len(args) == 1:
            return args[0]

        # Commutativity: A & B = B & A, A | B = B | A
        if sort:
            args.sort()

        # Create new (now canonical) expression.
        expr = self.__class__(*args)
        expr.iscanonical = True
        return expr

    def flatten(self):
        """
        Return a new expression where nested terms of this expression are
        flattened as far as possible.

        E.g.::

            A & (B & C) becomes A & B & C.
        """
        args = list(self.args)
        i = 0
        for arg in self.args:
            if isinstance(arg, self.__class__):
                args[i : i + 1] = arg.args
                i += len(arg.args)
            else:
                i += 1

        return self.__class__(*args)

    def absorb(self, args):
        """
        Given an `args` sequence of expressions, return a new list of expression
        applying absorption and negative absorption.

        See https://en.wikipedia.org/wiki/Absorption_law

        Absorption::

            A & (A | B) = A, A | (A & B) = A

        Negative absorption::

            A & (~A | B) = A & B, A | (~A & B) = A | B
        """
        args = list(args)
        if not args:
            args = list(self.args)
        i = 0
        while i < len(args):
            absorber = args[i]
            j = 0
            while j < len(args):
                if j == i:
                    j += 1
                    continue
                target = args[j]
                if not isinstance(target, self.dual):
                    j += 1
                    continue

                # Absorption
                if absorber in target:
                    del args[j]
                    if j < i:
                        i -= 1
                    continue

                # Negative absorption
                neg_absorber = self.NOT(absorber).cancel()
                if neg_absorber in target:
                    b = target.subtract(neg_absorber, simplify=False)
                    if b is None:
                        del args[j]
                        if j < i:
                            i -= 1
                        continue
                    else:
                        if b in args:
                            del args[j]
                            if j < i:
                                i -= 1
                        else:
                            args[j] = b
                        j += 1
                        continue

                if isinstance(absorber, self.dual):
                    remove = None
                    for arg in absorber.args:
                        narg = self.NOT(arg).cancel()
                        if arg in target.args:
                            pass
                        elif narg in target.args:
                            if remove is None:
                                remove = narg
                            else:
                                remove = None
                                break
                        else:
                            remove = None
                            break
                    if remove is not None:
                        args[j] = target.subtract(remove, simplify=True)
                j += 1
            i += 1

        return args

    def subtract(self, expr, simplify):
        """
        Return a new expression where the `expr` expression has been removed
        from this expression if it exists.
        """
        args = self.args
        if expr in self.args:
            args = list(self.args)
            args.remove(expr)
        elif isinstance(expr, self.__class__):
            if all(arg in self.args for arg in expr.args):
                args = tuple(arg for arg in self.args if arg not in expr)
        if len(args) == 0:
            return None
        if len(args) == 1:
            return args[0]

        newexpr = self.__class__(*args)
        if simplify:
            newexpr = newexpr.simplify()
        return newexpr

    def distributive(self):
        """
        Return a term where the leading AND or OR terms are switched.

        This is done by applying the distributive laws::

            A & (B|C) = (A&B) | (A&C)
            A | (B&C) = (A|B) & (A|C)
        """
        dual = self.dual
        args = list(self.args)
        for i, arg in enumerate(args):
            if isinstance(arg, dual):
                args[i] = arg.args
            else:
                args[i] = (arg,)

        prod = itertools.product(*args)
        args = tuple(self.__class__(*arg).simplify() for arg in prod)

        if len(args) == 1:
            return args[0]
        else:
            return dual(*args)

    def __lt__(self, other):
        comparator = Expression.__lt__(self, other)
        if comparator is not NotImplemented:
            return comparator

        if isinstance(other, self.__class__):
            lenself = len(self.args)
            lenother = len(other.args)
            for i in range(min(lenself, lenother)):
                if self.args[i] == other.args[i]:
                    continue

                comparator = self.args[i] < other.args[i]
                if comparator is not NotImplemented:
                    return comparator

            if lenself != lenother:
                return lenself < lenother
        return NotImplemented

    def __call__(self, **kwargs):
        """
        Return the evaluation of this expression by calling each of its arg as
        arg(**kwargs) and applying its corresponding Python operator (and or or)
        to the results.

        Reduce is used as in e.g. AND(a, b, c, d) == AND(a, AND(b, AND(c, d)))
        ore.g. OR(a, b, c, d) == OR(a, OR(b, OR(c, d)))
        """
        return reduce(self._pyoperator, (a(**kwargs) for a in self.args))


class AND(DualBase):
    """
    Boolean AND operation, taking two or more arguments.

    It can also be created by using "&" between two boolean expressions.

    You can subclass to define alternative string representation by overriding
    self.operator.
    
    For example:

    >>> class AND2(AND):
    ...     def __init__(self, *args):
    ...         super(AND2, self).__init__(*args)
    ...         self.operator = 'AND'
    """

    _pyoperator = and_operator

    def __init__(self, arg1, arg2, *args):
        super(AND, self).__init__(arg1, arg2, *args)
        self.sort_order = 10
        self.identity = self.TRUE
        self.annihilator = self.FALSE
        self.dual = self.OR
        self.operator = "&"


class OR(DualBase):
    """
    Boolean OR operation, taking two or more arguments

    It can also be created by using "|" between two boolean expressions.

    You can subclass to define alternative string representation by overriding
    self.operator.

    For example:

    >>> class OR2(OR):
    ...     def __init__(self, *args):
    ...         super(OR2, self).__init__(*args)
    ...         self.operator = 'OR'
    """

    _pyoperator = or_operator

    def __init__(self, arg1, arg2, *args):
        super(OR, self).__init__(arg1, arg2, *args)
        self.sort_order = 25
        self.identity = self.FALSE
        self.annihilator = self.TRUE
        self.dual = self.AND
        self.operator = "|"
