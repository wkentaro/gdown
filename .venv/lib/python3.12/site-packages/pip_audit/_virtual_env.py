"""
Create virtual environments with a custom set of packages and inspect their dependencies.
"""

from __future__ import annotations

import json
import logging
import venv
from collections.abc import Iterator
from os import PathLike
from tempfile import NamedTemporaryFile, TemporaryDirectory, gettempdir
from types import SimpleNamespace

from packaging.version import Version

from ._state import AuditState
from ._subprocess import CalledProcessError, run

logger = logging.getLogger(__name__)


class VirtualEnv(venv.EnvBuilder):
    """
    A wrapper around `EnvBuilder` that allows a custom `pip install` command to be executed, and its
    resulting dependencies inspected.

    The `pip-audit` API uses this functionality internally to deduce what the dependencies are for a
    given requirements file since this can't be determined statically.

    The `create` method MUST be called before inspecting the `installed_packages` property otherwise
    a `VirtualEnvError` will be raised.

    The expected usage is:
    ```
    # Create a virtual environment and install the `pip-api` package.
    ve = VirtualEnv(["pip-api"])
    ve.create(".venv/")
    for (name, version) in ve.installed_packages:
        print(f"Installed package {name} ({version})")
    ```
    """

    def __init__(
        self,
        install_args: list[str],
        index_url: str | None = None,
        extra_index_urls: list[str] = [],
        state: AuditState = AuditState(),
    ):
        """
        Create a new `VirtualEnv`.

        `install_args` is the list of arguments that would be used the custom install command. For
        example, if you wanted to execute `pip install -e /tmp/my_pkg`, you would create the
        `VirtualEnv` like so:
        ```
        ve = VirtualEnv(["-e", "/tmp/my_pkg"])
        ```

        `index_url` is the base URL of the package index.

        `extra_index_urls` are the extra URLs of package indexes.

        `state` is an `AuditState` to use for state callbacks.
        """
        super().__init__(with_pip=True)
        self._install_args = install_args
        self._index_url = index_url
        self._extra_index_urls = extra_index_urls
        self._packages: list[tuple[str, Version]] | None = None
        self._state = state

    def create(self, env_dir: str | bytes | PathLike[str] | PathLike[bytes]) -> None:
        """
        Creates the virtual environment.
        """

        try:
            return super().create(env_dir)
        except PermissionError:
            # `venv` uses a subprocess internally to bootstrap pip, but
            # some Linux distributions choose to mark the system temporary
            # directory as `noexec`. Apart from having only nominal security
            # benefits, this completely breaks our ability to execute from
            # within the temporary virtualenv.
            #
            # We may be able to hack around this in the future, but doing so
            # isn't straightforward or reliable. So we bail for now.
            #
            # See: https://github.com/pypa/pip-audit/issues/732
            base_tmpdir = gettempdir()
            raise VirtualEnvError(
                f"Couldn't execute in a temporary directory under {base_tmpdir}. "
                "This is sometimes caused by a noexec mount flag or other setting. "
                "Consider changing this setting or explicitly specifying a different "
                "temporary directory via the TMPDIR environment variable."
            )

    def post_setup(self, context: SimpleNamespace) -> None:
        """
        Install the custom package and populate the list of installed packages.

        This method is overridden from `EnvBuilder` to execute immediately after the virtual
        environment has been created and should not be called directly.

        We do a few things in our custom post-setup:
        - Upgrade the `pip` version. We'll be using `pip list` with the `--format json` option which
          requires a non-ancient version for `pip`.
        - Install `wheel`. When our packages install their own dependencies, they might be able
          to do so through wheels, which are much faster and don't require us to run
          setup scripts.
        - Execute the custom install command.
        - Call `pip list`, and parse the output into a list of packages to be returned from when the
          `installed_packages` property is queried.
        """
        self._state.update_state("Updating pip installation in isolated environment")

        # Firstly, upgrade our `pip` versions since `ensurepip` can leave us with an old version
        # and install `wheel` in case our package dependencies are offered as wheels
        # TODO: This is probably replaceable with the `upgrade_deps` option on `EnvBuilder`
        # itself, starting with Python 3.9.
        pip_upgrade_cmd = [
            context.env_exe,
            "-m",
            "pip",
            "install",
            "--upgrade",
            "pip",
            "wheel",
            "setuptools",
        ]
        try:
            run(pip_upgrade_cmd, state=self._state)
        except CalledProcessError as cpe:
            raise VirtualEnvError(f"Failed to upgrade `pip`: {pip_upgrade_cmd}") from cpe

        self._state.update_state("Installing package in isolated environment")

        with TemporaryDirectory() as ve_dir, NamedTemporaryFile(dir=ve_dir, delete=False) as tmp:
            # We use delete=False in creating the tempfile to allow it to be
            # closed and opened multiple times within the context scope on
            # windows, see GitHub issue #646.

            # Install our packages
            # NOTE(ww): We pass `--no-input` to prevent `pip` from indefinitely
            # blocking on user input for repository credentials, and
            # `--keyring-provider=subprocess` to allow `pip` to access the `keyring`
            # program on the `$PATH` for index credentials, if necessary. The latter flag
            # is required beginning with pip 23.1, since `--no-input` disables the default
            # keyring behavior.
            package_install_cmd = [
                context.env_exe,
                "-m",
                "pip",
                "install",
                "--no-input",
                "--keyring-provider=subprocess",
                *self._index_url_args,
                "--dry-run",
                "--report",
                tmp.name,
                *self._install_args,
            ]
            try:
                run(package_install_cmd, log_stdout=True, state=self._state)
            except CalledProcessError as cpe:
                # TODO: Propagate the subprocess's error output better here.
                logger.error(f"internal pip failure: {cpe.stderr}")
                raise VirtualEnvError(f"Failed to install packages: {package_install_cmd}") from cpe

            self._state.update_state("Processing package list from isolated environment")

            install_report = json.load(tmp)
            package_list = install_report["install"]

            # Convert into a series of name, version pairs
            self._packages = []
            for package in package_list:
                package_metadata = package["metadata"]
                self._packages.append(
                    (package_metadata["name"], Version(package_metadata["version"]))
                )

    @property
    def installed_packages(self) -> Iterator[tuple[str, Version]]:
        """
        A property to inspect the list of packages installed in the virtual environment.

        This method can only be called after the `create` method has been called.
        """
        if self._packages is None:
            raise VirtualEnvError(
                "Invalid usage of wrapper."
                "The `create` method must be called before inspecting `installed_packages`."
            )

        yield from self._packages

    @property
    def _index_url_args(self) -> list[str]:
        args = []
        if self._index_url:
            args.extend(["--index-url", self._index_url])
        for index_url in self._extra_index_urls:
            args.extend(["--extra-index-url", index_url])
        return args


class VirtualEnvError(Exception):
    """
    Raised when `VirtualEnv` fails to build or inspect dependencies, for any reason.
    """

    pass
