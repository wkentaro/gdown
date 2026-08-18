# Docker Image Distribution

gdown will not ship a `Dockerfile` or publish a container image to a registry.

## Why this is out of scope

Containers earn their place when a tool carries compiled extensions, system
libraries, or a service runtime. gdown has none of these. It is a pure-Python
CLI with five pure-Python dependencies and no build step, so `pip install gdown`
and `uvx gdown <url>` already cover running it without a prior setup, and both
finish faster than pulling a multi-arch image.

Running gdown through a container also makes its interface worse. Every
invocation needs a bind mount or the downloaded file disappears when the
container exits. Cookies need a second bind mount onto the fixed path
`~/.cache/gdown/cookies.txt`, and that file must stay writable by the container
user because the cookie jar is rewritten after each download. Output files land
on the host owned by the container UID. Documenting all of this took 55 lines
in a 238-line README, a 23% increase, for a distribution path that does less
than the bare command.

Publishing to a registry adds permanent maintenance the project does not
otherwise carry: a release artifact tied to every push and tag, base image
upgrades, vulnerability reports filed against published images, slow emulated
multi-architecture builds, and users pinning a floating tag.

The narrow real case is a CI runner or scheduled job with no Python available.
Those users can write a four-line Dockerfile over the published package, which
is a smaller cost to them than an official image is to this project.

## Prior requests

- [PR #473](https://github.com/wkentaro/gdown/pull/473) - Add Docker support for
  gdown with multi-arch build and usage instructions
