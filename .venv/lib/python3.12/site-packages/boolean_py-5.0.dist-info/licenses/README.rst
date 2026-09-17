boolean.py
==========

"boolean.py" is a small library implementing a boolean algebra. It
defines two base elements, TRUE and FALSE, and a Symbol class that can
take on one of these two values. Calculations are done in terms of AND,
OR and NOT - other compositions like XOR and NAND are not implemented
but can be emulated with AND or and NOT. Expressions are constructed
from parsed strings or in Python.

It runs on Python 3.6+
You can use older version 3.x for Python 2.7+ support.

https://github.com/bastikr/boolean.py

Build status: |Build Status|


Example
-------

::

    >>> import boolean
    >>> algebra = boolean.BooleanAlgebra()
    >>> expression1 = algebra.parse(u'apple and (oranges or banana) and not banana', simplify=False)
    >>> expression1
    AND(Symbol('apple'), OR(Symbol('oranges'), Symbol('banana')), NOT(Symbol('banana')))

    >>> expression2 = algebra.parse('(oranges | banana) and not banana & apple', simplify=True)
    >>> expression2
    AND(Symbol('apple'), NOT(Symbol('banana')), Symbol('oranges'))

    >>> expression1 == expression2
    False
    >>> expression1.simplify() == expression2
    True


Documentation
-------------

http://readthedocs.org/docs/booleanpy/en/latest/


Installation
------------

Installation via pip
~~~~~~~~~~~~~~~~~~~~

To install boolean.py, you need to have the following pieces of software
on your computer:

-  Python 3.6+
-  pip

You then only need to run the following command:

``pip install boolean.py``


Installation via package managers
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

There are packages available for easy install on some operating systems.
You are welcome to help us package this tool for more distributions!

-  boolean.py has been packaged as Arch Linux, Fedora, openSus,
   nixpkgs, Guix, DragonFly and FreeBSD 
   `packages <https://repology.org/project/python:boolean.py/versions>`__ .

In particular:

-  Arch Linux (AUR):
   `python-boolean.py <https://aur.archlinux.org/packages/python-boolean.py/>`__
-  Fedora:
   `python-boolean.py <https://apps.fedoraproject.org/packages/python-boolean.py>`__
-  openSUSE:
   `python-boolean.py <https://software.opensuse.org/package/python-boolean.py>`__


Testing
-------

Test ``boolean.py`` with your current Python environment:

``python setup.py test``

Test with all of the supported Python environments using ``tox``:

::

    pip install -r requirements-dev.txt
    tox

If ``tox`` throws ``InterpreterNotFound``, limit it to python
interpreters that are actually installed on your machine:

::

    tox -e py36

Alternatively use pytest.


License
-------

Copyright (c) Sebastian Kraemer, basti.kr@gmail.com and others
SPDX-License-Identifier: BSD-2-Clause

.. |Build Status| image:: https://travis-ci.org/bastikr/boolean.py.svg?branch=master
   :target: https://travis-ci.org/bastikr/boolean.py
