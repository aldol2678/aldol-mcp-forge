"""Bounded, descriptor-relative reads; requires POSIX no-follow support.

No path-based fallback: unsupported platforms fail closed. A read-only mount
is still required against malicious concurrent writers / mount changes.
"""
from contextlib import contextmanager
import os
from pathlib import Path
import stat


def _identity(info):
    return info.st_dev, info.st_ino


def _snapshot(info):
    return (_identity(info), info.st_mode, info.st_nlink, info.st_size,
            info.st_mtime_ns, info.st_ctime_ns)


@contextmanager
def directory(name, parent_fd=None):
    if not all(hasattr(os, flag) for flag in ("O_NOFOLLOW", "O_DIRECTORY", "O_NONBLOCK")):
        raise OSError("safe filesystem operations unavailable")
    before = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    if not stat.S_ISDIR(before.st_mode):
        raise OSError("not a directory")
    fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                 dir_fd=parent_fd)
    try:
        if _identity(before) != _identity(os.fstat(fd)):
            raise OSError("directory changed")
        yield fd
        after = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        if _identity(before) != _identity(after):
            raise OSError("directory replaced")
    finally:
        os.close(fd)


@contextmanager
def workspace(path: Path):
    # Anchor every component, including parents of the configured root.
    from contextlib import ExitStack
    with ExitStack() as stack:
        fd = stack.enter_context(directory(path.anchor))
        for part in path.parts[1:]:
            fd = stack.enter_context(directory(part, fd))
        yield fd


def read_file(parent_fd, name, limit):
    before = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    if (not stat.S_ISREG(before.st_mode) or before.st_size > limit
            or before.st_nlink != 1):
        raise OSError("unsafe file")
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                 dir_fd=parent_fd)
    try:
        opened = os.fstat(fd)
        if _snapshot(before) != _snapshot(opened):
            raise OSError("file replaced before read")
        chunks, remaining = [], limit + 1
        while remaining:
            chunk = os.read(fd, min(remaining, 16384))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        after = os.fstat(fd)
        named = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        if (remaining == 0 or _snapshot(opened) != _snapshot(after)
                or _snapshot(opened) != _snapshot(named)):
            raise OSError("file changed during read")
        return b"".join(chunks), opened
    finally:
        os.close(fd)
