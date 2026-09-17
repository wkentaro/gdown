Changelog
=========

v30.4.4 - 2025-01-10
--------------------

This is a minor release with license udpates:

- Update license list to latest ScanCode and SPDX 3.27

v30.4.3 - 2025-06-25
--------------------

This is a minor bugfix release:

- Release license-expression wheels properly

v30.4.2 - 2025-06-25
--------------------

This is a minor release without API changes:

- Use latest skeleton
- Update license list to latest ScanCode


v30.4.1 - 2025-01-10
--------------------

This is a minor release without API changes:

- Use latest skeleton
- Update license list to latest ScanCode and SPDX 3.26


v30.4.0 - 2024-10-21
--------------------

This is a minor release without API changes:

- Use latest skeleton
- Update license list to latest ScanCode and SPDX 3.25
- Drop support for Python 3.8

v30.3.1 - 2024-08-13
--------------------

This is a minor release without API changes:

- Update link references of ownership from nexB to aboutcode-org

v30.3.0 - 2024-03-18
--------------------

This is a minor release without API changes:

- Use latest skeleton
- Update license list to latest ScanCode and SPDX 3.23
- Drop support for Python 3.7

v30.2.0 - 2023-11-29
--------------------

This is a minor release without API changes:

- Use latest skeleton
- Update license list to latest ScanCode and SPDX 3.22
- Add Python 3.12 support in CI


v30.1.1 - 2023-01-16
----------------------

This is a minor dot release without API changes

- Use latest skeleton
- Update license list to latest ScanCode and SPDX 3.20


v30.1.0 - 2023-01-16
----------------------

This is a minor release without API changes

- Use latest skeleton (and updated configure script)
- Update license list to latest ScanCode and SPDX 3.19
- Use correct syntax for python_require
- Drop using Travis and Appveyor
- Drop support for Python 3.7 and add Python 3.11 in CI


v30.0.0 - 2022-05-10
----------------------

This is a minor release with API changes

- Use latest skeleton (and updated configure script)
- Drop using calver
- Improve error checking when combining licenses



v21.6.14 - 2021-06-14
----------------------

Added
~~~~~

- Switch to calver for package versioning to better convey the currency of the
  bundled data.

- Include https://scancode-licensedb.aboutcode.org/ licenses list with
  ScanCode (v21.6.7) and SPDX licenses (v3.13) keys. Add new functions to
  create Licensing using these licenses as LicenseSymbol.

- Add new License.dedup() method to deduplicate and simplify license expressions
  without over simplifying.

- Add new License.validate() method to return a new ExpressionInfo object with
  details on a license expression validation.


Changed
~~~~~~~
- Drop support for Python 2.
- Adopt the project skeleton from https://github.com/nexB/skeleton
  and its new configure script


v1.2 - 2019-11-14
------------------
Added
~~~~~
- Add ability to render WITH expression wrapped in parenthesis

Fixes
~~~~~
- Fix anomalous backslashes in strings

Changed
~~~~~~~
- Update the thirdparty directory structure.


v1.0 - 2019-10-16
------------------
Added
~~~~~
- New version of boolean.py library
- Add ability to leave license expressions unsorted when simplifying

Changed
~~~~~~~
- updated travis CI settings


v0.999 - 2019-04-29
--------------------
- Initial release
- license-expression is small utility library to parse, compare and
  simplify and normalize license expressions.

