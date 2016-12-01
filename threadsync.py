# coding: utf-8

import threading
import contextlib

# A private extension to threading.Event
class EventTAS(type(threading.Event())):
    def __init__(self, *args, **kwargs):
        super(EventTAS, self).__init__(*args, **kwargs)
        self.mutex = threading.Lock()

    def set(self, *args, **kwargs):
        with self.mutex:
            prevflag = self.is_set()
            super(EventTAS, self).set(*args, **kwargs)
        return prevflag

    def clear(self, *args, **kwargs):
        with self.mutex:
            prevflag = self.is_set()
            super(EventTAS, self).clear(*args, **kwargs)
        return prevflag



# Still no RW Lock in python...
# FIXME: Make the lock recursive?
class RWLock(object):
    """A read-write lock with priority to writers. Usable with "with". The
    default behavior is to acquire the read lock."""

    class ThreadLockingInfos(threading.local):
        def __init__(self):
            super(RWLock.ThreadLockingInfos, self).__init__()
            self.reading = False
            self.writing = False


    def __init__(self, mutex = None):
        self.mutex = mutex if mutex is not None else threading.Lock()
        self.readq = threading.Condition(self.mutex)
        self.writeq = threading.Condition(self.mutex)
        self.readercount = 0
        self.writercount = 0
        self.writing = False

        # Thread-local storage
        self.tls = self.ThreadLockingInfos()


    # Must be called with self.mutex locked
    def _acquire_read(self):
        # Just wait for writers to wake us
        while self.writercount > 0:
            self.readq.wait()
        self.readercount += 1
        self.tls.reading = True

    def acquire_read(self):
        """Acquire a reading lock."""
        assert(not self.tls.reading)
        with self.mutex:
            self._acquire_read()

    __enter__ = acquire_read


    # Must be called with self.mutex locked
    def _release_read(self):
        self.tls.reading = False
        self.readercount -= 1

        # Last reader wake the writers
        if self.readercount == 0:
            self.writeq.notify()

    def release_read(self):
        """Release a reading lock."""
        assert(self.tls.reading)
        with self.mutex:
            self._release_read()

    def __exit__(self, t, v, tb):
        self.release_read()


    # Must be called with self.mutex locked
    def _acquire_write(self):
        self.writercount += 1
        while self.readercount > 0 or self.writing:
            self.writeq.wait()

        self.writing = True
        self.tls.writing = True

    def acquire_write(self):
        """Acquire a writing lock."""
        assert(not self.tls.writing)
        with self.mutex:
            self._acquire_write()


    # Must be called with self.mutex locked
    def _release_write(self):
        self.writercount -= 1
        self.writing = False
        self.tls.writing = False

        if self.writercount > 0:
            self.writeq.notify()
        else:
            self.readq.notify_all()

    def release_write(self):
        """Release a writing lock."""
        assert(self.tls.writing)
        with self.mutex:
            self._release_write()


    def upgrade_write(self):
        """Change a reading lock to a writer lock."""
        assert(self.tls.reading)
        assert(not self.tls.writing)
        with self.mutex:
            self._release_read()
            self._acquire_write()


    def downgrade_write(self):
        """Change a writing lock to a reader lock."""
        assert(self.tls.writing)
        assert(not self.tls.reading)
        with self.mutex:
            self._release_write()
            self._acquire_read()


    @contextlib.contextmanager
    def read(self):
        """Context manager to be used in a "with" statement.
        Acquire a read lock for the duration of the execution of the block."""
        self.acquire_read()
        try:
            yield self
        finally:
            self.release_read()


    @contextlib.contextmanager
    def write(self):
        """Context manager to be used in a "with" statement.
        Acquire a write lock for the duration of the execution of the block.
        Upgrade if the lock was held for reading."""

        is_upgrade = self.tls.reading

        if is_upgrade:
            self.upgrade_write()
        else:
            self.acquire_write()

        try:
            yield self
        finally:
            if is_upgrade:
                self.downgrade_write()
            else:
                self.release_write()


    @contextlib.contextmanager
    def downgrade(self):
        """Context manager to be used in a "with" statement.
        Change a write lock to a read lock for the duration of the execution of
        the block."""
        self.downgrade_write()
        try:
            yield self
        finally:
            self.upgrade_write()


    @contextlib.contextmanager
    def unlock(self):
        """Context manager to be used in a "with" statement.
        Release completely a lock for the duration of the execution of the
        block. Reacquires it as before afterwards."""
        was_reading = self.tls.reading
        was_writing = self.tls.writing

        if was_writing:
            self.release_write()
        if was_reading:
            self.release_read()
        try:
            yield self
        finally:
            if was_reading:
                self.acquire_read()
            if was_writing:
                self.acquiwre_write()
