import json
import os
from typing import Dict, List, Optional

import pip_api
from pip_api._call import call
from pip_api._vendor.packaging_legacy.version import parse  # type: ignore


class Distribution:
    def __init__(
        self,
        name: str,
        version: str,
        location: Optional[str] = None,
        editable_project_location: Optional[str] = None,
    ):
        self.name = name
        self.version = parse(version)
        self.location = location
        self.editable_project_location = editable_project_location

        if pip_api.PIP_VERSION >= parse("21.3"):
            self.editable = bool(self.editable_project_location)
        else:
            self.editable = bool(self.location)

    def __repr__(self):
        return "<Distribution(name='{}', version='{}'{}{})>".format(
            self.name,
            self.version,
            ", location='{}'".format(self.location) if self.location else "",
            (
                ", editable_project_location='{}'".format(
                    self.editable_project_location
                )
                if self.editable_project_location
                else ""
            ),
        )


def installed_distributions(
    local: bool = False, paths: List[os.PathLike] = []
) -> Dict[str, Distribution]:
    list_args = ["list", "-v", "--format=json"]
    if local:
        list_args.append("--local")
    for path in paths:
        list_args.extend(["--path", str(path)])
    result = call(*list_args)

    ret = {}

    # The returned JSON is an array of objects, each of which looks like this:
    # { "name": "some-package", "version": "0.0.1", "location": "/path/", ... }
    # The location key was introduced with pip 10.0.0b1, so we don't assume its
    # presence. The editable_project_location key was introduced with pip 21.3,
    # so we also don't assume its presence.
    for raw_dist in json.loads(result):
        dist = Distribution(
            raw_dist["name"],
            raw_dist["version"],
            raw_dist.get("location"),
            raw_dist.get("editable_project_location"),
        )
        ret[dist.name] = dist

    return ret
