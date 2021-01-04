"""

    Greynir: Natural language processing for Icelandic

    GlobalLock utility class

    Copyright (C) 2021 Miðeind ehf.
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
    interprocess locks within a server.

    A GlobalLock is implemented as a file in the /tmp/ directory,
    which is assumed to exist (on the current drive in Windows).

    A quick and easy way to use a blocking GlobalLock is as follows:

    with GlobalLock('somestring'):
        code_that_only_one_process_can_run_simultaneously()

"""

import os
import stat
import tempfile


class LockError(Exception):
    """ Lock could not be obtained """
    pass


POSIX = False

try:
    # Try Linux/POSIX
    import fcntl
except ImportError:

    try:
        # Try Windows
        import msvcrt
    except ImportError:

        # Not Unix, not Windows: bail out
        def _lock_file(file, block):
            raise TypeError("File locking not supported on this platform")

        def _unlock_file(file):
            raise TypeError("File locking not supported on this platform")

    else:

        # Windows

        def _lock_file(file, block):
            # Lock just the first byte of the file
            retry = True
            while retry:
                retry = False
                try:
                    msvcrt.locking(
                        file.fileno(), msvcrt.LK_LOCK if block else msvcrt.LK_NBLCK, 1
                    )
                except OSError as e:
                    if block and e.errno == 36:
                        # Windows says 'resource deadlock avoided', but we truly want
                        # a longer blocking wait: try again
                        retry = True
                    else:
                        raise LockError(
                            "Couldn't lock {0}, errno is {1}".format(file.name, e.errno)
                        )

        def _unlock_file(file):
            try:
                file.seek(0)
                msvcrt.locking(file.fileno(), msvcrt.LK_UNLCK, 1)
            except OSError as e:
                raise LockError(
                    "Couldn't unlock {0}, errno is {1}".format(file.name, e.errno)
                )

else:

    # Linux/POSIX

    POSIX = True

    def _lock_file(file, block):
        try:
            fcntl.flock(file.fileno(), fcntl.LOCK_EX | (0 if block else fcntl.LOCK_NB))
        except IOError:
            raise LockError("Couldn't lock {0}".format(file.name))

    def _unlock_file(file):
        # File is automatically unlocked on close
        pass


class GlobalLock:

    _TMP_DIR = tempfile.gettempdir()

    def __init__(self, lockname):
        """ Initialize a global lock with the given name """
        assert lockname and isinstance(lockname, str)
        # Locate global locks in the system temporary directory
        # (should work on both Windows and Unix/POSIX)
        self._path = os.path.join(self._TMP_DIR, "greynir-" + lockname)
        self._fp = None

    def acquire(self, block=True):
        """ Acquire a global lock, blocking if block = True """

        if self._fp is not None:
            # Already hold the lock
            return

        path = self._path
        fp = None
        try:
            # Try to open for writing without truncation:
            fp = open(path, "r+")
        except IOError:
            # If the file doesn't exist, we'll get an IO error, try a+
            # Note that there may be a race here. Multiple processes
            # could fail on the r+ open and open the file a+, but only
            # one will get the the lock and write a pid.
            fp = open(path, "a+")
            # Make sure that the file is readable and writable by others
            if POSIX and fp is not None:
                os.fchmod(
                    fp.fileno(),
                    stat.S_IRUSR | stat.S_IWUSR
                    | stat.S_IRGRP | stat.S_IWGRP
                    | stat.S_IROTH | stat.S_IWOTH
                )

        if fp is None:
            raise LockError("Couldn't open or create lock file {0}".format(path))

        self._fp = fp

        try:
            _lock_file(fp, block)
        except:
            fp.seek(1)
            fp.close()
            raise

        # Once acquired, write the process id to the file
        fp.write(" %s\n" % os.getpid())
        fp.truncate()
        fp.flush()

    def release(self):
        """ Release the lock """
        if self._fp is not None:
            _unlock_file(self._fp)
            self._fp.close()
            self._fp = None

    def __enter__(self):
        """ Python context manager protocol """
        self.acquire(block=True)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """ Python context manager protocol """
        self.release()
        return False
