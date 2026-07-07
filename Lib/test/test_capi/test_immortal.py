import sys
import unittest
from test.support import import_helper

_testcapi = import_helper.import_module('_testcapi')
_testinternalcapi = import_helper.import_module('_testinternalcapi')


class TestUnstableCAPI(unittest.TestCase):
    def test_immortal(self):
        # Not extensive
        known_immortals = (True, False, None, 0, ())
        for immortal in known_immortals:
            with self.subTest(immortal=immortal):
                self.assertTrue(_testcapi.is_immortal(immortal))

        # Some arbitrary mutable objects
        non_immortals = (object(), self, [object()])
        for non_immortal in non_immortals:
            with self.subTest(non_immortal=non_immortal):
                self.assertFalse(_testcapi.is_immortal(non_immortal))

        # CRASHES _testcapi.is_immortal(NULL)

    def test_ordinary_object_not_immortal_after_many_increfs(self):
        # gh-153202: the free-threaded immortal marker no longer lives in
        # ob_ref_local (whose width is being reduced), so an ordinary object
        # whose reference count is incremented well past 250 from a single
        # thread must not be misreported as immortal.
        obj = object()
        # Build many references from this single thread. This drives the
        # owning-thread incref fast path far above 250 references.
        refs = [obj] * 300
        try:
            self.assertGreaterEqual(sys.getrefcount(obj), 250)
            self.assertFalse(_testcapi.is_immortal(obj))
        finally:
            del refs
        self.assertFalse(_testcapi.is_immortal(obj))


class TestInternalCAPI(unittest.TestCase):

    def test_immortal_builtins(self):
        for obj in range(-5, 1025):
            self.assertTrue(_testinternalcapi.is_static_immortal(obj))
        self.assertTrue(_testinternalcapi.is_static_immortal(None))
        self.assertTrue(_testinternalcapi.is_static_immortal(False))
        self.assertTrue(_testinternalcapi.is_static_immortal(True))
        self.assertTrue(_testinternalcapi.is_static_immortal(...))
        self.assertTrue(_testinternalcapi.is_static_immortal(()))
        for obj in range(1025, 1125):
            self.assertFalse(_testinternalcapi.is_static_immortal(obj))
        for obj in ([], {}, set()):
            self.assertFalse(_testinternalcapi.is_static_immortal(obj))


if __name__ == "__main__":
    unittest.main()
