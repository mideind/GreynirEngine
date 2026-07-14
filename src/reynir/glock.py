"""

    Greynir: Natural language processing for Icelandic

    GlobalLock utility class

    Copyright © 2023 Miðeind ehf.
    Original author: Vilhjálmur Þorsteinsson

    This software is licensed under the MIT License:

        Permission is hereby granted, free of charge, to any person
        obtaining a copy of this software and associated documentation
        files (the "Software"), to deal in the Software without restriction,
        including without limitation the rights to use, copy, modify, merge,
        publish, distribute, sublicense, and/or sell copies of the Software,
        and to permit persons to whom the Software is furnished to do so,
        subject to the following conditions:

        The above copyright notice and this permission notice shall be
        included in all copies or substantial portions of the Software.

        THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
        EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
        MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
        IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
        CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
        TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
        SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

    This module implements the GlobalLock class, providing
    named interprocess locks within a single machine.

    Note: this class is no longer used by GreynirEngine itself, which
    uses the cross-platform filelock package directly (see fastparser.py).
    GlobalLock is retained as a thin wrapper around filelock for backwards
    compatibility with external code that imports it.

    A GlobalLock is implemented as a lock file in the system temporary
    directory.

    A quick and easy way to use a blocking GlobalLock is as follows:

    with GlobalLock('somestring'):
        code_that_only_one_process_can_run_simultaneously()

"""

from typing import Any

import os
import tempfile

from filelock import FileLock, Timeout


class LockError(Exception):
    """Lock could not be obtained"""

    pass


class GlobalLock:
    """A named interprocess lock, implemented as a lock file
    in the system temporary directory"""

    def __init__(self, lockname: str) -> None:
        """Initialize a global lock with the given name"""
        assert lockname and isinstance(lockname, str)
        # Locate global locks in the system temporary directory,
        # using the same file name as previous versions of this module
        self._lock = FileLock(
            os.path.join(tempfile.gettempdir(), "greynir-" + lockname)
        )

    def acquire(self, block: bool = True) -> None:
        """Acquire a global lock, blocking if block = True"""
        if self._lock.is_locked:
            # This process already holds the lock
            return
        try:
            self._lock.acquire(timeout=-1 if block else 0)
        except Timeout:
            raise LockError("Couldn't lock {0}".format(self._lock.lock_file))

    def release(self) -> None:
        """Release the lock"""
        if self._lock.is_locked:
            self._lock.release()

    def __enter__(self) -> "GlobalLock":
        """Python context manager protocol"""
        self.acquire(block=True)
        return self

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> None:
        """Python context manager protocol"""
        self.release()
