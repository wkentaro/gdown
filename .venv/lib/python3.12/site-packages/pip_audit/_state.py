"""
Interfaces for for propagating feedback from the API to provide responsive progress indicators as
well as a progress spinner implementation for use with CLI applications.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from collections.abc import Sequence
from logging.handlers import MemoryHandler
from typing import Any

from rich.align import StyleType
from rich.console import Console, Group, RenderableType
from rich.live import Live
from rich.panel import Panel
from rich.status import Spinner


class AuditState:
    """
    An object that handles abstract "updates" to `pip-audit`'s state.

    Non-UI consumers of `pip-audit` (via `pip_audit`) should have no need for
    this class, and can leave it as a default construction in whatever signatures
    it appears in. Its primary use is internal and UI-specific: it exists solely
    to give the CLI enough state for a responsive progress indicator during
    user requests.
    """

    def __init__(self, *, members: Sequence[_StateActor] = []):
        """
        Create a new `AuditState` with the given member list.
        """

        self._members = members

    def update_state(self, message: str, logs: str | None = None) -> None:
        """
        Called whenever `pip_audit`'s internal state changes in a way that's meaningful to
        expose to a user.

        `message` is the message to present to the user.
        """

        for member in self._members:
            member.update_state(message, logs)

    def initialize(self) -> None:
        """
        Called when `pip-audit`'s state is initializing.
        """

        for member in self._members:
            member.initialize()

    def finalize(self) -> None:
        """
        Called when `pip_audit`'s state is "done" changing.
        """
        for member in self._members:
            member.finalize()

    def __enter__(self) -> AuditState:  # pragma: no cover
        """
        Create an instance of the `pip-audit` state for usage within a `with` statement.
        """

        self.initialize()
        return self

    def __exit__(
        self, _exc_type: Any, _exc_value: Any, _exc_traceback: Any
    ) -> None:  # pragma: no cover
        """
        Helper to ensure `finalize` gets called when the `pip-audit` state falls out of scope of a
        `with` statement.
        """
        self.finalize()


class _StateActor(ABC):
    @abstractmethod
    def update_state(self, message: str, logs: str | None = None) -> None:
        raise NotImplementedError  # pragma: no cover

    @abstractmethod
    def initialize(self) -> None:
        """
        Called when `pip-audit`'s state is initializing. Implementors should
        override this to do nothing if their state management requires no
        initialization step.
        """
        raise NotImplementedError  # pragma: no cover

    @abstractmethod
    def finalize(self) -> None:
        """
        Called when the overlaying `AuditState` is "done," i.e. `pip-audit`'s
        state is done changing. Implementors should override this to do nothing
        if their state management requires no finalization step.
        """
        raise NotImplementedError  # pragma: no cover


class StatusLog:  # pragma: no cover
    """
    Displays a status indicator with an optional log panel to display logs
    for external processes.

    This code is based off of Rich's `Status` component:
        https://github.com/Textualize/rich/blob/master/rich/status.py
    """

    # NOTE(alex): We limit the panel to 10 characters high and display the last 10 log lines.
    # However, the panel won't display all 10 of those lines if some of the lines are long enough
    # to wrap in the panel.
    LOG_PANEL_HEIGHT = 10

    def __init__(
        self,
        status: str,
        *,
        console: Console | None = None,
        spinner: str = "dots",
        spinner_style: StyleType = "status.spinner",
        speed: float = 1.0,
        refresh_per_second: float = 12.5,
    ):
        """
        Construct a new `StatusLog`.

        `status` is the status message to display next to the spinner.
        `console` is the Rich console to display the log status in.
        `spinner` is the name of the spinner animation (see python -m rich.spinner). Defaults to `dots`.
        `spinner_style` is the style of the spinner. Defaults to `status.spinner`.
        `speed` is the speed factor for the spinner animation. Defaults to 1.0.
        `refresh_per_second` is the number of refreshes per second. Defaults to 12.5.
        """

        self._spinner = Spinner(spinner, text=status, style=spinner_style, speed=speed)
        self._log_panel = Panel("", height=self.LOG_PANEL_HEIGHT)
        self._live = Live(
            self.renderable,
            console=console,
            refresh_per_second=refresh_per_second,
            transient=True,
        )

    @property
    def renderable(self) -> RenderableType:
        """
        Create a Rich renderable type for the log panel.

        If the log panel contains text, we should create a group and place the
        log panel underneath the spinner.
        """

        if self._log_panel.renderable:
            return Group(self._spinner, self._log_panel)
        return self._spinner

    def update(
        self,
        status: str,
        logs: str | None,
    ) -> None:
        """
        Update status and logs.
        """

        if logs is None:
            logs = ""
        else:
            # Limit the logging output to the 10 most recent lines.
            logs = "\n".join(logs.splitlines()[-self.LOG_PANEL_HEIGHT :])
        self._spinner.update(text=status)
        self._log_panel.renderable = logs
        self._live.update(self.renderable, refresh=True)

    def start(self) -> None:
        """
        Start the status animation.
        """

        self._live.start()

    def stop(self) -> None:
        """
        Stop the spinner animation.
        """

        self._live.stop()

    def __rich__(self) -> RenderableType:
        """
        Convert to a Rich renderable type.
        """

        return self.renderable


class AuditSpinner(_StateActor):  # pragma: no cover
    """
    A progress spinner for `pip-audit`, using `rich.status`'s spinner support
    under the hood.
    """

    def __init__(self, message: str = "") -> None:
        """
        Initialize the `AuditSpinner`.
        """

        self._console = Console()
        # NOTE: audits can be quite fast, so we need a pretty high refresh rate here.
        self._spinner = StatusLog(
            message, console=self._console, spinner="line", refresh_per_second=30
        )

        # Keep the target set to `None` to ensure that the logs don't get written until the spinner
        # has finished writing output, regardless of the capacity argument
        self.log_handler = MemoryHandler(
            0, flushLevel=logging.ERROR, target=None, flushOnClose=False
        )
        self.prev_handlers: list[logging.Handler] = []

    def update_state(self, message: str, logs: str | None = None) -> None:
        """
        Update the spinner's state.
        """

        self._spinner.update(message, logs)

    def initialize(self) -> None:
        """
        Redirect logging to an in-memory log handler so that it doesn't get mixed in with the
        spinner output.
        """

        # Remove all existing log handlers
        #
        # We're recording them here since we'll want to restore them once the spinner falls out of
        # scope
        root_logger = logging.root
        for handler in root_logger.handlers:
            self.prev_handlers.append(handler)
        for handler in self.prev_handlers:
            root_logger.removeHandler(handler)

        # Redirect logging to our in-memory handler that will buffer the log lines
        root_logger.addHandler(self.log_handler)

        self._spinner.start()

    def finalize(self) -> None:
        """
        Cleanup the spinner output so it doesn't get combined with subsequent `stderr` output and
        flush any logs that were recorded while the spinner was active.
        """

        self._spinner.stop()

        # Now that the spinner is complete, flush the logs
        root_logger = logging.root
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(logging.Formatter(logging.BASIC_FORMAT))
        self.log_handler.setTarget(stream_handler)
        self.log_handler.flush()

        # Restore the original log handlers
        root_logger.removeHandler(self.log_handler)
        for handler in self.prev_handlers:
            root_logger.addHandler(handler)
