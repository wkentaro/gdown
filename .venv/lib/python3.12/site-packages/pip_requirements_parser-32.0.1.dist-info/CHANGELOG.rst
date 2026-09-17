Changelog
=========


v32.0.1
-------

Ensure all tests pass correctly.
Adopt latest skelton

Add new RequirementsFile.from_string() convenience factory method

Vendor LegacyVersion from pre V2 packaging. Otherwise packaging v2 broke
this library and its dependencies.


v32.0.0
-------

Emergency pin of packaging to version under 22.
This breaks this library and its dependents otherwise



v31.1.1
-------

Add new tests. No other changes.


v31.1.0
-------

Add new convenience method InstallRequirement.get_pinned_version() to return
the pinned version if there is such thing.


v31.0.1
-------

Fix twine warning wrt. long_description content type.


v31.0.0
-------

Include code in wheel. This was not included otherwise.
Improve documentation


v30.0.0
-------

Initial release based on pip at commit 5cf98408f48a0ef91d61aea56485a7a83f6bbfa8
e.g., https://github.com/pypa/pip/tree/5cf98408f48a0ef91d61aea56485a7a83f6bbfa8
