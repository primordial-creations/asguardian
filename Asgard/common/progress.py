"""
Progress Reporting Infrastructure

Provides progress indicators for long-running operations.
Supports spinners, progress bars, and status updates.
"""

import sys
import time
from threading import Event, Thread
from typing import Iterator, List, Optional, TypeVar

from Asgard.common._progress_types import ProgressConfig, ProgressStyle

T = TypeVar('T')


class ProgressReporter:
    """
    Progress reporter for long-running operations.

    Usage:
        # As context manager
        with ProgressReporter("Processing files", total=100) as progress:
            for item in items:
                process(item)
                progress.advance()

        # With iterator
        for item in ProgressReporter.iterate(items, "Processing"):
            process(item)

        # Manual control
        progress = ProgressReporter("Scanning", total=50)
        progress.start()
        for i, item in enumerate(items):
            progress.update(i + 1, f"File: {item.name}")
            process(item)
        progress.finish()
    """

    SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    DOTS_FRAMES = [".", "..", "...", ""]

    def __init__(
        self,
        message: str = "Processing",
        total: Optional[int] = None,
        config: Optional[ProgressConfig] = None,
    ):
        """
        Initialize the progress reporter.

        Args:
            message: Base message to display
            total: Total number of items (for percentage)
            config: Progress configuration
        """
        self.message = message
        self.total = total
        self.config = config or ProgressConfig()

        self._current = 0
        self._status = ""
        self._start_time: Optional[float] = None
        self._stop_event = Event()
        self._thread: Optional[Thread] = None
        self._frame = 0

    def __enter__(self) -> "ProgressReporter":
        """Start progress reporting."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Stop progress reporting."""
        self.finish(success=exc_type is None)

    @classmethod
    def iterate(
        cls,
        items: List[T],
        message: str = "Processing",
        config: Optional[ProgressConfig] = None,
    ) -> Iterator[T]:
        """
        Iterate over items with progress reporting.

        Args:
            items: Items to iterate over
            message: Progress message
            config: Progress configuration

        Yields:
            Items from the list
        """
        with cls(message, total=len(items), config=config) as progress:
            for item in items:
                yield item
                progress.advance()

    def start(self) -> None:
        """Start the progress indicator."""
        if not self.config.enabled or self.config.style == ProgressStyle.NONE:
            return

        self._start_time = time.time()
        self._stop_event.clear()

        if self.config.style in (ProgressStyle.SPINNER, ProgressStyle.DOTS):
            self._thread = Thread(target=self._animate, daemon=True)
            self._thread.start()
        else:
            self._render()

    def stop(self) -> None:
        """Stop the progress indicator."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=1.0)
            self._thread = None

    def finish(self, success: bool = True) -> None:
        """Finish progress reporting with final status."""
        self.stop()

        if not self.config.enabled or self.config.style == ProgressStyle.NONE:
            return

        # Clear the line
        self._clear_line()

        # Print final status
        elapsed = self._elapsed_str()
        icon = "✓" if success else "✗"

        if self.total:
            print(f"{icon} {self.message}: {self._current}/{self.total} ({elapsed})")
        else:
            print(f"{icon} {self.message} ({elapsed})")

    def update(self, current: int, status: str = "") -> None:
        """
        Update progress.

        Args:
            current: Current count
            status: Optional status message
        """
        self._current = current
        self._status = status

        if self.config.style == ProgressStyle.BAR:
            self._render()

    def advance(self, count: int = 1, status: str = "") -> None:
        """
        Advance progress by count.

        Args:
            count: Number to advance by
            status: Optional status message
        """
        self.update(self._current + count, status)

    def set_status(self, status: str) -> None:
        """Set the current status message."""
        self._status = status

    def _animate(self) -> None:
        """Animation loop for spinner/dots."""
        while not self._stop_event.is_set():
            self._render()
            time.sleep(self.config.refresh_rate)
            self._frame = (self._frame + 1) % len(self._get_frames())

    def _get_frames(self) -> List[str]:
        """Get animation frames for current style."""
        if self.config.style == ProgressStyle.DOTS:
            return self.DOTS_FRAMES
        return self.SPINNER_FRAMES

    def _render(self) -> None:
        """Render the current progress state."""
        if not self.config.enabled:
            return

        self._clear_line()

        if self.config.style == ProgressStyle.BAR:
            line = self._render_bar()
        elif self.config.style == ProgressStyle.SPINNER:
            line = self._render_spinner()
        elif self.config.style == ProgressStyle.DOTS:
            line = self._render_dots()
        else:
            line = self.message

        sys.stdout.write(line)
        sys.stdout.flush()

    def _render_spinner(self) -> str:
        """Render spinner style."""
        frame = self.SPINNER_FRAMES[self._frame % len(self.SPINNER_FRAMES)]
        parts = [f"\r{frame} {self.message}"]

        if self.config.show_count and self.total:
            parts.append(f" [{self._current}/{self.total}]")
        elif self.config.show_count and self._current > 0:
            parts.append(f" [{self._current}]")

        if self.config.show_percentage and self.total and self.total > 0:
            pct = (self._current / self.total) * 100
            parts.append(f" {pct:.0f}%")

        if self.config.show_elapsed:
            parts.append(f" ({self._elapsed_str()})")

        if self._status:
            parts.append(f" - {self._status}")

        return "".join(parts)

    def _render_bar(self) -> str:
        """Render progress bar style."""
        parts = [f"\r{self.message}: "]

        if self.total and self.total > 0:
            pct = self._current / self.total
            filled = int(self.config.bar_width * pct)
            empty = self.config.bar_width - filled

            bar = "█" * filled + "░" * empty
            parts.append(f"[{bar}]")

            if self.config.show_percentage:
                parts.append(f" {pct * 100:.0f}%")

            if self.config.show_count:
                parts.append(f" ({self._current}/{self.total})")
        else:
            parts.append(f"[{'░' * self.config.bar_width}]")
            if self.config.show_count:
                parts.append(f" ({self._current})")

        if self.config.show_elapsed:
            parts.append(f" {self._elapsed_str()}")

        if self._status:
            parts.append(f" - {self._status}")

        return "".join(parts)

    def _render_dots(self) -> str:
        """Render dots style."""
        dots = self.DOTS_FRAMES[self._frame % len(self.DOTS_FRAMES)]
        parts = [f"\r{self.message}{dots}"]

        if self.config.show_count and self._current > 0:
            parts.append(f" ({self._current})")

        return "".join(parts)

    def _elapsed_str(self) -> str:
        """Get elapsed time as string."""
        if not self._start_time:
            return "0s"

        elapsed = time.time() - self._start_time

        if elapsed < 60:
            return f"{elapsed:.1f}s"
        elif elapsed < 3600:
            mins = int(elapsed // 60)
            secs = int(elapsed % 60)
            return f"{mins}m {secs}s"
        else:
            hours = int(elapsed // 3600)
            mins = int((elapsed % 3600) // 60)
            return f"{hours}h {mins}m"

    def _clear_line(self) -> None:
        """Clear the current line."""
        sys.stdout.write("\r" + " " * 80 + "\r")
        sys.stdout.flush()


def with_progress(
    items: List[T],
    message: str = "Processing",
    style: ProgressStyle = ProgressStyle.SPINNER,
) -> Iterator[T]:
    """
    Convenience function to iterate with progress.

    Args:
        items: Items to iterate over
        message: Progress message
        style: Progress style

    Yields:
        Items from the list
    """
    config = ProgressConfig(style=style)
    yield from ProgressReporter.iterate(items, message, config)


def spinner(message: str = "Loading") -> ProgressReporter:
    """
    Create a simple spinner.

    Args:
        message: Message to display

    Returns:
        ProgressReporter configured as spinner
    """
    return ProgressReporter(message, config=ProgressConfig(style=ProgressStyle.SPINNER))


def progress_bar(message: str = "Processing", total: int = 100) -> ProgressReporter:
    """
    Create a progress bar.

    Args:
        message: Message to display
        total: Total count

    Returns:
        ProgressReporter configured as progress bar
    """
    return ProgressReporter(
        message,
        total=total,
        config=ProgressConfig(style=ProgressStyle.BAR),
    )
