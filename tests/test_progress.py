from __future__ import annotations

import io

from wsf.progress import Progress


def test_progress_writes_status_then_line() -> None:
    stream = io.StringIO()
    progress = Progress(enabled=True, stream=stream)
    progress.status("gdelt incident 2022-02-03 [1/21] downloading 8/96")
    progress.line("gdelt incident 2022-02-03 [1/21] ok count=12")
    text = stream.getvalue()
    assert "downloading 8/96" in text
    assert "ok count=12" in text
    assert text.endswith("ok count=12\033[K\n")


def test_silent_progress_writes_nothing() -> None:
    stream = io.StringIO()
    progress = Progress(enabled=False, stream=stream)
    progress.status("secret")
    progress.line("secret")
    assert stream.getvalue() == ""
