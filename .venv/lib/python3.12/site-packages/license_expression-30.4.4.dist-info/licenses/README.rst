==================
license-expression
==================

``license-expression`` is a comprehensive utility library to parse, compare,
simplify and normalize license expressions (such as SPDX license expressions)
using boolean logic.

- License: Apache-2.0
- Python: 3.9+
- Homepage: https://github.com/aboutcode-org/license-expression/
- Install: `pip install license-expression` also available in most Linux distro.

Software project licenses are often a combination of several free and open
source software licenses. License expressions -- as specified by SPDX -- provide
a concise and human readable way to express these licenses without having to
read long license texts, while still being machine-readable.

License expressions are used by key FOSS projects such as Linux; several
packages ecosystem use them to document package licensing metadata such as
npm and Rubygems; they are important when exchanging software data (such as with
SPDX and SBOM in general) as a way to express licensing precisely.

``license-expression`` is a comprehensive utility library to parse, compare,
simplify and normalize these license expressions (such as SPDX license expressions)
using boolean logic like in: `GPL-2.0-or-later WITH Classpath-exception-2.0 AND MIT`.

It includes the license keys from SPDX https://spdx.org/licenses/ (version 3.26)
and ScanCode LicenseDB (from scancode-toolkit version 32.3.1, last published on 2025-01-10).
See https://scancode-licensedb.aboutcode.org/ to get started quickly.

``license-expression`` is both powerful and simple to use and is a used as the
license expression engine in several projects and products such as:

- AboutCode-toolkit https://github.com/aboutcode-org/aboutcode-toolkit
- AlekSIS (School Information System) https://edugit.org/AlekSIS/official/AlekSIS-Core
- Conda forge tools https://github.com/conda-forge/conda-smithy
- DejaCode https://enterprise.dejacode.com
- DeltaCode https://github.com/nexB/deltacode
- FenixscanX https://github.com/SmartsYoung/FenixscanX
- FetchCode https://github.com/aboutcode-org/fetchcode
- Flict https://github.com/vinland-technology/flict and https://github.com/vinland-technology
- license.sh https://github.com/webscopeio/license.sh
- liferay_inbound_checker https://github.com/carmenbianca/liferay_inbound_checker
- REUSE https://reuse.software/ and https://github.com/fsfe/reuse-tool
- ScanCode-io https://github.com/aboutcode-org/scancode.io
- ScanCode-toolkit https://github.com/aboutcode-org/scancode-toolkit
- SecObserve https://github.com/MaibornWolff/SecObserve

See also for details:
- https://spdx.github.io/spdx-spec/v2.3/SPDX-license-expressions

``license-expression`` is also packaged for most Linux distributions. See below.

Alternative:

There is no known alternative library for Python, but there are several similar
libraries in other languages (but not as powerful of course!):

- JavaScript https://github.com/jslicense/spdx-expression-parse.js
- Rust https://github.com/ehuss/license-exprs
- Haskell https://github.com/phadej/spdx
- Go https://github.com/kyoh86/go-spdx
- Ada https://github.com/Fabien-Chouteau/spdx_ada
- Java https://github.com/spdx/tools and https://github.com/aschet/spdx-license-expression-tools

Source code and download
========================

- GitHub https://github.com/aboutcode-org/license-expression.git
- PyPI https://pypi.python.org/pypi/license-expression

Also available in several Linux distros:

- Arch Linux https://archlinux.org/packages/extra/any/python-license-expression/
- Debian https://packages.debian.org/unstable/source/license-expression
- DragonFly BSD https://github.com/DragonFlyBSD/DPorts/tree/master/textproc/py-license-expression
- Fedora https://src.fedoraproject.org/rpms/python-license-expression/
- FreeBSD https://www.freshports.org/textproc/py-license-expression
- NixOS https://github.com/NixOS/nixpkgs/blob/release-21.05/pkgs/development/python-modules/license-expression/default.nix
- openSUSE https://build.opensuse.org/package/show/openSUSE:Factory/python-license-expression


Support
=======

- Submit bugs and questions at: https://github.com/aboutcode-org/license-expression/issues
- Join the chat at: https://gitter.im/aboutcode-org/discuss

Description
===========

This module defines a mini language to parse, validate, simplify, normalize and
compare license expressions using a boolean logic engine.

This supports SPDX license expressions and also accepts other license naming
conventions and license identifiers aliases to resolve and normalize any license
expressions.

Using boolean logic, license expressions can be tested for equality, containment,
equivalence and can be normalized or simplified.

It also bundles the SPDX License list (3.26 as of now) and the ScanCode license
DB (based on latest ScanCode) to easily parse and validate expressions using
the license symbols.


Usage examples
==============

The main entry point is the ``Licensing`` object that you can use to parse,
validate, compare, simplify and normalize license expressions.

Create an SPDX Licensing and parse expressions::

    >>> from license_expression import get_spdx_licensing
    >>> licensing = get_spdx_licensing()
    >>> expression = ' GPL-2.0 or LGPL-2.1 and mit '
    >>> parsed = licensing.parse(expression)
    >>> print(parsed.pretty())
    OR(
      LicenseSymbol('GPL-2.0-only'),
      AND(
        LicenseSymbol('LGPL-2.1-only'),
        LicenseSymbol('MIT')
      )
    )

    >>> str(parsed)
    'GPL-2.0-only OR (LGPL-2.1-only AND MIT)'

    >>> licensing.parse('unknwon with foo', validate=True, strict=True)
    license_expression.ExpressionParseError: A plain license symbol cannot be used
    as an exception in a "WITH symbol" statement. for token: "foo" at position: 13

    >>> licensing.parse('unknwon with foo', validate=True)
    license_expression.ExpressionError: Unknown license key(s): unknwon, foo

    >>> licensing.validate('foo and MIT and GPL-2.0+')
    ExpressionInfo(
        original_expression='foo and MIT and GPL-2.0+',
        normalized_expression=None,
        errors=['Unknown license key(s): foo'],
        invalid_symbols=['foo']
    )


Create a simple Licensing and parse expressions::

    >>> from license_expression import Licensing, LicenseSymbol
    >>> licensing = Licensing()
    >>> expression = ' GPL-2.0 or LGPL-2.1 and mit '
    >>> parsed = licensing.parse(expression)
    >>> expression = ' GPL-2.0 or LGPL-2.1 and mit '
    >>> expected = 'GPL-2.0-only OR (LGPL-2.1-only AND mit)'
    >>> assert str(parsed) == expected
    >>> assert parsed.render('{symbol.key}') == expected


Create a Licensing with your own license symbols::

    >>> expected = [
    ...   LicenseSymbol('GPL-2.0'),
    ...   LicenseSymbol('LGPL-2.1'),
    ...   LicenseSymbol('mit')
    ... ]
    >>> assert licensing.license_symbols(expression) == expected
    >>> assert licensing.license_symbols(parsed) == expected

    >>> symbols = ['GPL-2.0+', 'Classpath', 'BSD']
    >>> licensing = Licensing(symbols)
    >>> expression = 'GPL-2.0+ with Classpath or (bsd)'
    >>> parsed = licensing.parse(expression)
    >>> expected = 'GPL-2.0+ WITH Classpath OR BSD'
    >>> assert parsed.render('{symbol.key}') == expected

    >>> expected = [
    ...   LicenseSymbol('GPL-2.0+'),
    ...   LicenseSymbol('Classpath'),
    ...   LicenseSymbol('BSD')
    ... ]
    >>> assert licensing.license_symbols(parsed) == expected
    >>> assert licensing.license_symbols(expression) == expected

And expression can be deduplicated, to remove duplicate license subexpressions
without changing the order and without consider license choices as simplifiable::

    >>> expression2 = ' GPL-2.0 or (mit and LGPL 2.1) or bsd Or GPL-2.0  or (mit and LGPL 2.1)'
    >>> parsed2 = licensing.parse(expression2)
    >>> str(parsed2)
    'GPL-2.0 OR (mit AND LGPL 2.1) OR BSD OR GPL-2.0 OR (mit AND LGPL 2.1)'
    >>> assert str(parsed2.simplify()) == 'BSD OR GPL-2.0 OR (LGPL 2.1 AND mit)'

Expression can be simplified, treating them as boolean expressions::

    >>> expression2 = ' GPL-2.0 or (mit and LGPL 2.1) or bsd Or GPL-2.0  or (mit and LGPL 2.1)'
    >>> parsed2 = licensing.parse(expression2)
    >>> str(parsed2)
    'GPL-2.0 OR (mit AND LGPL 2.1) OR BSD OR GPL-2.0 OR (mit AND LGPL 2.1)'
    >>> assert str(parsed2.simplify()) == 'BSD OR GPL-2.0 OR (LGPL 2.1 AND mit)'

Two expressions can be compared for equivalence and containment:

    >>> expr1 = licensing.parse(' GPL-2.0 or (LGPL 2.1 and mit) ')
    >>> expr2 = licensing.parse(' (mit and LGPL 2.1)  or GPL-2.0 ')
    >>> licensing.is_equivalent(expr1, expr2)
    True
    >>> licensing.is_equivalent(' GPL-2.0 or (LGPL 2.1 and mit) ',
    ...                         ' (mit and LGPL 2.1)  or GPL-2.0 ')
    True
    >>> expr1.simplify() == expr2.simplify()
    True
    >>> expr3 = licensing.parse(' GPL-2.0 or mit or LGPL 2.1')
    >>> licensing.is_equivalent(expr2, expr3)
    False
    >>> expr4 = licensing.parse('mit and LGPL 2.1')
    >>> expr4.simplify() in expr2.simplify()
    True
    >>> licensing.contains(expr2, expr4)
    True

Development
===========

- Checkout a clone from https://github.com/aboutcode-org/license-expression.git

- Then run ``./configure --dev`` and then ``source tmp/bin/activate`` on Linux and POSIX.
  This will install all dependencies in a local virtualenv, including
  development deps.

- On Windows run  ``configure.bat --dev`` and then ``Scripts\bin\activate`` instead.

- To run the tests, run ``pytest -vvs``
