
Changelog
=========


next
----

5.0 (2025-04-03)
----------------

* API changes

 * Drop support for Python versions older than 3.9.
 * Add support by testing on Python 3.11 to 3.14
 * Fix absorption issues https://github.com/bastikr/boolean.py/issues/111 and
   https://github.com/bastikr/boolean.py/issues/112



4.0 (2022-05-05)
----------------

* API changes

 * Drop support for Python 2.
 * Test on Python 3.10
 * Make Expression.sort_order an instance attributes and not a class attribute

* Misc.

 * Correct licensing documentation
 * Improve docstringf and apply minor refactorings
 * Adopt black code style and isort for imports
 * Drop Travis and use GitHub actions for CI


3.8 (2020-06-10)
----------------

* API changes

 * Add support for evaluation of boolean expression.
   Thank you to Lars van Gemerden @gemerden

* Bug fixes

 * Fix parsing of tokens that have a number as the first character. 
   Thank you to Jeff Cohen @ jcohen28
 * Restore proper Python 2 compatibility. 
   Thank you to Benjy Weinberger @benjyw

* Improve documentation

 * Add pointers to Linux distro packages.
   Thank you to Max Mehl @mxmehl and Carmen Bianca Bakker @carmenbianca
 * Fix typo.
   Thank you to Gabriel Niebler @der-gabe


3.7 (2019-10-04)
----------------

* API changes

 * Add new sort argument to simplify() to optionally not sort when simplifying
   expressions (e.g. not applying "commutativity"). Thank you to Steven Esser
   @majurg for this
 * Add new argument to tokenizer to optionally accept extra characters in symbol
   tokens. Thank you to @carpie for this


3.6 (2018-08-06)
----------------

* No API changes

* Bug fixes

 * Fix De Morgan's laws effect on double negation propositions. Thank you to Douglas Cardoso for this
 * Improve error checking when parsing


3.5 (Nov 1, 2017)
-----------------

* No API changes

* Bug fixes

 * Documentation updates and add testing for Python 3.6. Thank you to Alexander Lisianoi @alisianoi
 * Improve testng and expression equivalence checks
 * Improve subs() method to an expression 

 

3.4 (May 12, 2017)
------------------

* No API changes

* Bug fixes and improvements

 * Fix various documentation typos and improve tests . Thank you to Alexander Lisianoi @alisianoi
 * Fix handling for literals vs. symbols in negations Thank you to @YaronK


3.3 (2017-02-09)
----------------

* API changes

 * #40 and #50 Expression.subs() now takes 'default' thanks to @kronuz
 * #45 simplify=False is now the default for parse and related functions or methods.
 * #40 Use "&" and "|" as default operators

* Bug fixes

 * #60 Fix bug for "a or b c" which is not a valid expression
 * #58 Fix math formula display in docs
 * Improve handling of parse errors


2.0.0 (2016-05-11)
------------------

* API changes

 * New algebra definition. Refactored class hierarchy. Improved parsing.

* New features

 * possibility to subclass algebra definition
 * new normal forms shortcuts for DNF and CNF.


1.1 (2016-04-06)
------------------

* Initial release on Pypi.
