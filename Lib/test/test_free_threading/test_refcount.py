import sys
import threading
import unittest

from test.support import import_helper, threading_helper


_testcapi = import_helper.import_module("_testcapi")


@threading_helper.requires_working_threading()
class TestRefcountOverflowSpill(unittest.TestCase):
    def test_concurrent_incref_overflow_spill(self):
        # gh-153202: In the free-threaded build ``ob_ref_local`` is a uint8_t,
        # so it can only hold a small (< 256) local reference count.  When the
        # owning thread increments an object's reference count past that
        # ~256-entry boundary, the excess must "spill" into the shared
        # reference count -- it must never overflow the field or immortalize
        # the object.
        #
        # Drive one object's reference count far past the boundary from the
        # owning thread (exercising the overflow-spill path many times) while
        # several other threads concurrently create and drop references through
        # the shared reference count, then confirm the final reference count is
        # exactly correct and the object was not immortalized.
        #
        # The reference-count assertions are only made once every worker thread
        # has been joined, so the object's state is quiescent and the expected
        # count is deterministic (this makes the test robust against re-runs;
        # it is intended to pass with no flakiness across many consecutive
        # runs, e.g. ``-F --forever``).

        class C:
            pass

        # ``obj`` is created here, so it is owned by the thread running this
        # test.  Only *this* thread's increfs use the narrow local count and
        # can trigger the overflow-spill path, so the owner workload below must
        # run on this thread rather than in a spawned worker.
        obj = C()

        NUM_WORKERS = 8
        # Comfortably larger than the 256-entry local boundary so the owning
        # thread crosses it (and spills) many times.
        NUM_REFS = 5000

        # References held permanently by the owning thread for the duration of
        # the measurement.  Building these drives the owner-thread local count
        # far past 256, forcing repeated spills into the shared count.
        owner_refs = []

        # Synchronize the owner and all workers so the spill path and the
        # shared-count increfs genuinely race.
        barrier = threading.Barrier(NUM_WORKERS + 1)

        def worker():
            # A non-owning thread: each incref goes through the atomic shared
            # reference count.  Every reference taken here is dropped again, so
            # once the thread is joined it has contributed a net zero to the
            # reference count.
            barrier.wait()
            held = []
            for _ in range(NUM_REFS):
                held.append(obj)
            del held

        threads = [threading.Thread(target=worker) for _ in range(NUM_WORKERS)]
        for thread in threads:
            thread.start()

        # Baseline includes the local ``obj`` name plus the temporary reference
        # created for the ``sys.getrefcount`` argument.
        base = sys.getrefcount(obj)

        barrier.wait()
        for _ in range(NUM_REFS):
            owner_refs.append(obj)

        for thread in threads:
            thread.join()

        # Every worker has been joined, so their references are gone and only
        # the owner's ``NUM_REFS`` references (plus the baseline) remain.
        self.assertEqual(sys.getrefcount(obj), base + NUM_REFS)

        # The overflow must have spilled into the shared count, not
        # immortalized the object.
        self.assertFalse(_testcapi.is_immortal(obj))

        # Dropping the owner's references brings the count back to the baseline,
        # confirming the spilled shared count is accounted for on decref.
        owner_refs.clear()
        self.assertEqual(sys.getrefcount(obj), base)
        self.assertFalse(_testcapi.is_immortal(obj))


if __name__ == "__main__":
    unittest.main()
