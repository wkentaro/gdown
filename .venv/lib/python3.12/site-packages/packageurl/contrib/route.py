# -*- coding: utf-8 -*-
#
# Copyright (c) the purl authors
# SPDX-License-Identifier: MIT

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

# Visit https://github.com/package-url/packageurl-python for support and
# download.

import inspect
import re
from functools import wraps

"""
Given a URI regex (or some string), this module can route execution to a
callable.

There are several routing implementations available in Rails, Django, Flask,
Paste, etc. However, these all assume that the routed processing is to craft a
response to an incoming external HTTP request.

Here we are instead doing the opposite: given a URI (and no request yet) we are
routing the processing to emit a request externally (HTTP or other protocol)
and handling its response.

Also we crawl a lot and not only HTTP: git, svn, ftp, rsync and more.
This simple library support this kind of arbitrary URI routing.

This is inspired by Guido's http://www.artima.com/weblogs/viewpost.jsp?thread=101605
and Django, Flask, Werkzeug and other url dispatch and routing design from web
frameworks.
https://github.com/douban/brownant has a similar approach, using
Werkzeug with the limitation that it does not route based on URI scheme and is
limited to HTTP.
"""


class Rule(object):
    """
    A rule is a mapping between a pattern (typically a URI) and a callable
    (typically a function).
    The pattern is a regex string pattern and must match entirely a string
    (typically a URI) for the rule to be considered, i.e. for the endpoint to
    be resolved and eventually invoked for a given string (typically a URI).
    """

    def __init__(self, pattern, endpoint):
        # To ensure the pattern will match entirely, we wrap the pattern
        # with start of line ^ and  end of line $.
        self.pattern = pattern.lstrip("^").rstrip("$")
        self.pattern_match = re.compile("^" + self.pattern + "$").match

        # ensure the endpoint is callable
        assert callable(endpoint)
        # classes are not always callable, make an extra check
        if inspect.isclass(endpoint):
            obj = endpoint()
            assert callable(obj)

        self.endpoint = endpoint

    def __repr__(self):
        return f'Rule(r"""{self.pattern}""", {self.endpoint.__module__}.{self.endpoint.__name__})'

    def match(self, string):
        """
        Match a string with the rule pattern, return True is matching.
        """
        return self.pattern_match(string)


class RouteAlreadyDefined(TypeError):
    """
    Raised when this route Rule already exists in the route map.
    """


class NoRouteAvailable(TypeError):
    """
    Raised when there are no route available.
    """


class MultipleRoutesDefined(TypeError):
    """
    Raised when there are more than one route possible.
    """


class Router(object):
    """
    A router is:
    - a container for a route map, consisting of several rules, stored in an
     ordered dictionary keyed by pattern text
    - a way to process a route, i.e. given a string (typically a URI), find the
     correct rule and invoke its callable endpoint
    - and a convenience decorator for routed callables (either a function or
     something with a __call__ method)

    Multiple routers can co-exist as needed, such as a router to collect,
    another to fetch, etc.
    """

    def __init__(self, route_map=None):
        """
        'route_map' is an ordered mapping of pattern -> Rule.
        """
        self.route_map = route_map or dict()
        # lazy cached pre-compiled regex match() for all route patterns
        self._is_routable = None

    def __repr__(self):
        return repr(self.route_map)

    def __iter__(self):
        return iter(self.route_map.items())

    def keys(self):
        return self.route_map.keys()

    def append(self, pattern, endpoint):
        """
        Append a new pattern and endpoint Rule at the end of the map.
        Use this as an alternative to the route decorator.
        """
        if pattern in self.route_map:
            raise RouteAlreadyDefined(pattern)
        self.route_map[pattern] = Rule(pattern, endpoint)

    def route(self, *patterns):
        """
        Decorator to make a callable 'endpoint' routed to one or more patterns.

        Example:
        >>> my_router = Router()
        >>> @my_router.route('http://nexb.com', 'http://deja.com')
        ... def somefunc(uri):
        ...    pass
        """

        def decorator(endpoint):
            assert patterns
            for pat in patterns:
                self.append(pat, endpoint)

            @wraps(endpoint)
            def decorated(*args, **kwargs):
                return self.process(*args, **kwargs)

            return decorated

        return decorator

    def process(self, string, *args, **kwargs):
        """
        Given a string (typically a URI), resolve this string to an endpoint
        by searching available rules then execute the endpoint callable for
        that string passing down all arguments to the endpoint invocation.
        """
        endpoint = self.resolve(string)
        if inspect.isclass(endpoint):
            # instantiate a class, that must define a __call__ method
            # TODO: consider passing args to the constructor?
            endpoint = endpoint()
        # call the callable
        return endpoint(string, *args, **kwargs)

    def resolve(self, string):
        """
        Resolve a string: given a string (typically a URI) resolve and
        return the best endpoint function for that string.

        Ambiguous resolution is not allowed in order to keep things in
        check when there are hundreds rules: if multiple routes are
        possible for a string (typically a URI), a MultipleRoutesDefined
        TypeError is raised.
        """
        # TODO: we could improve the performance of this by using a single
        # regex and named groups if this ever becomes a bottleneck.
        candidates = [r for r in self.route_map.values() if r.match(string)]

        if not candidates:
            raise NoRouteAvailable(string)

        if len(candidates) > 1:
            # this can happen when multiple patterns match the same string
            # we raise an exception with enough debugging information
            pats = repr([r.pattern for r in candidates])
            msg = "%(string)r matches multiple patterns %(pats)r" % locals()
            raise MultipleRoutesDefined(msg)

        return candidates[0].endpoint

    def is_routable(self, string):
        """
        Return True if `string` is routable by this router, e.g. if it
        matches any of the route patterns.
        """
        if not string:
            return

        if not self._is_routable:
            # build an alternation regex
            routables = "^(" + "|".join(pat for pat in self.route_map) + ")$"
            self._is_routable = re.compile(routables, re.UNICODE).match

        return bool(self._is_routable(string))
