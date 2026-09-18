pip-requirements-parser - a mostly correct pip requirements parsing library
================================================================================

Copyright (c) nexB Inc. and others.
Copyright (c) The pip developers (see AUTHORS.rst file)
SPDX-License-Identifier: MIT
Homepage: https://github.com/nexB/pip-requirements and https://www.aboutcode.org/


``pip-requirements-parser`` is a mostly correct pip requirements parsing
library ... because it uses pip's own code!

pip is the ``package installer`` for Python that is using "requirements" text
files listing the packages to install.

Per https://pip.pypa.io/en/stable/reference/requirements-file-format/ :

    "The requirements file format is closely tied to a number of internal
    details of pip (e.g., pip’s command line options). The basic format is
    relatively stable and portable but the full syntax, as described here,
    is only intended for consumption by pip, and other tools should take
    that into account before using it for their own purposes."

And per https://pip.pypa.io/en/stable/user_guide/#using-pip-from-your-program :

    "[..] pip is a command line program. While it is implemented in Python, and
    so is available from your Python code via import pip, you must not use pip’s
    internal APIs in this way."
    
    "What this means in practice is that everything inside of pip is considered
    an implementation detail. Even the fact that the import name is pip is
    subject to change without notice. While we do try not to break things as
    much as possible, all the internal APIs can change at any time, for any
    reason. It also means that we generally won’t fix issues that are a result
    of using pip in an unsupported way."


Because of all this, pip requirements are notoriously difficult to parse right
in all their diversity because:

- pip does not have a public API and therefore cannot be reliably used as a
  stable library. Some libraries attempt to do this though. (See Alternative)

- The pip requirements file syntax is closely aligned with pip's command line
  interface and command line options. In some ways a pip requirements file is a
  list of pip command line options and arguments. Therefore, it is hard to parse
  these short of reproducing the pip command line options parsing. At least one
  other library is using a command line option parser to parse options correctly.


This ``pip-requirements-parser`` Python library is yet another pip requirements
files parser, but this time doing it hopefully correctly and doing as well as
pip does it, because this is using pip's own code.


The ``pip-requirements-parser`` library offers these key advantages:

- Other requirements parsers typically do not work in all the cases that ``pip``
  supports: parsing any requirement as seen in the wild will fail parsing some
  valid pip requirements. Since the ``pip-requirements-parser`` library is based
  on pip's own code, it works **exactly** like pip and will parse all the
  requirements files that pip can parse.

- The ``pip-requirements-parser`` library offers a simple and stable code API
  that will not change without notice.

- The ``pip-requirements-parser`` library is designed to work offline without
  making any external network call, while the original pip code needs network
  access.

- The ``pip-requirements-parser`` library is a single file that can easily be
  copied around as needed for easy vendoring. This is useful as requirements
  parsing is often needed to bootstrap in a constrained environment.

- The ``pip-requirements-parser`` library has only one external dependency on
  the common "packaging" package. Otherwise it uses only the standard library.
  The benefits are the same as being a single file: fewer moving parts helps with
  using it in more cases.

- The ``pip-requirements-parser`` library reuses and passes the full subset of
  the pip test suite that deals with requirements. This is a not really
  surprising since this is pip's own code. The suite suite has been carefully
  ported and adjusted to work with the updated code subset.

- The standard pip requirements parser depends on the ``requests`` HTTP library
  and makes network connection to PyPI and other referenced repositories when
  parsing. The ``pip-requirements-parser`` library works entirely offline and the
  requests dependency and calling has been entirely removed.

- The ``pip-requirements-parser`` library has preserved the complete pip git
  history for the subset of the code we kept. The original pip code was merged
  from multiple modules keeping all the git history at the line/blame level using
  some git fu and git filter repo. The benefit is that we will be able to more
  easily track and merge future pip updates.

- The ``pip-requirements-parser`` library has an extensive test suite  made of:

  - pip's own tests
  - new unit tests
  - new requirements test files (over 40 new test files)
  - the tests suite of some of the main other requirement parsers including:

     - http://github.com/di/pip-api
     - https://github.com/pyupio/dparse
     - https://github.com/landscapeio/requirements-detector
     - https://github.com/madpah/requirements-parser

As a result, it has likely the most comprehensive requiremente parsing test
suite around.


Usage
~~~~~~~~~~

The entry point is the ``RequirementsFile`` object::

    >>> from pip_requirements_parser import RequirementsFile
    >>> rf = RequirementsFile.from_file("requirements.txt")

From there, you can dump to a dict::
    >>> rf.to_dict()

Or access the requirements (either InstallRequirement or EditableRequirement
objects)::

    >>> for req in rf.requirements:
    ...    print(req.to_dict())
    ...    print(req.dumps())

And the various other parsed elements such as options, commenst and invalid lines
that have a parsing error::

    >>> rf.options
    >>> rf.comment_lines
    >>> rf.invalid_lines

Each of these and the ``requirements`` hahve a "requirement_line" attribute
with the original text.

Finally you can get a requirements file back as a string::

    >>> rf.dumps()


Alternative
------------------

There are several other parsers that either:

- Implement their own parsing and can therefore miss some subtle differences
- Or wrap and import pip as a library, working around the lack of pip API

None of these use the approach of reusing and forking the subset of pip that is
needed to parse requirements.  The ones that wrap pip require network access
like pip does. They potentially need updating each time there is a new pip
release. The ones that reimplement pip parsing may not support all pip
specifics.


Implement a new pip parser
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- pip-api https://github.com/di/pip-api does not support hashes and certain pip options.
  It does however use argparse for parsing options and is therefore correctly
  handling most options. The parser is a single script that only depends on
  packaging (that is vendored). It is not designed to be used as a single script
  though and ``pip`` is a dependency.

- requirements-parser https://github.com/madpah/requirements-parse does not
  support hashes and certain pip options

- dparse https://github.com/pyupio/dparse

- https://github.com/GoogleCloudPlatform/django-cloud-deploy/blob/d316b1e45357761e2b124143e6e12ce34ef6f975/django_cloud_deploy/skeleton/requirements_parser.py


Reuse and wrap pip's own parser
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- requirementslib https://github.com/sarugaku/requirementslib uses pip-shim
  https://github.com/sarugaku/pip-shims which is a set of "shims" around each
  pip versions in an attempt to offer an API to pip. Comes with 20+ dependencies,

- micropipenv https://github.com/thoth-station/micropipenv/blob/d0c37c1bf0aadf5149aebe2df0bf1cb12ded4c40/micropipenv.py#L53

- pip-tools https://github.com/jazzband/pip-tools/blob/9e1be05375104c56e07cdb0904e1b50b86f8b550/piptools/_compat/pip_compat.py
