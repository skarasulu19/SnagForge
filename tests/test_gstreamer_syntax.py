"""Use the real GStreamer parser without capturing a desktop or encoding video."""
import ctypes
import ctypes.util
import unittest
from media import pipeline


class GError(ctypes.Structure):
    _fields_=[('domain',ctypes.c_uint),('code',ctypes.c_int),('message',ctypes.c_char_p)]


class PipelineSyntaxTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        gst=ctypes.util.find_library('gstreamer-1.0');glib=ctypes.util.find_library('glib-2.0')
        if not gst or not glib:raise unittest.SkipTest('GStreamer parser libraries are not installed.')
        cls.gst=ctypes.CDLL(gst);cls.glib=ctypes.CDLL(glib)
        cls.gst.gst_init.argtypes=[ctypes.c_void_p,ctypes.c_void_p];cls.gst.gst_init(None,None)
        cls.gst.gst_parse_launch.argtypes=[ctypes.c_char_p,ctypes.POINTER(ctypes.POINTER(GError))]
        cls.gst.gst_parse_launch.restype=ctypes.c_void_p
        cls.gst.gst_object_unref.argtypes=[ctypes.c_void_p]
        cls.glib.g_error_free.argtypes=[ctypes.POINTER(GError)]
        cls.gst.gst_element_factory_find.argtypes=[ctypes.c_char_p]
        cls.gst.gst_element_factory_find.restype=ctypes.c_void_p
        for name in (b'fakesrc',b'fakesink'):
            factory=cls.gst.gst_element_factory_find(name)
            if not factory:raise unittest.SkipTest('GStreamer core elements are not installed.')
            cls.gst.gst_object_unref(factory)

    def parse_error(self,description):
        error=ctypes.POINTER(GError)()
        parsed=self.gst.gst_parse_launch(description.encode(),ctypes.byref(error))
        try:return error.contents.message.decode() if error else None
        finally:
            if error:self.glib.g_error_free(error)
            if parsed:self.gst.gst_object_unref(parsed)

    def test_generated_video_format_and_rate_filter_parses(self):
        for fps in (15,30,60):
            for crop in (None,(20,40,60,80)):
                with self.subTest(fps=fps,crop=crop):
                    args=pipeline('/tmp/test.mp4','MP4 video',9,42,crop,'None',fps)
                    # Test the actual filter tokens emitted between the rate
                    # converter and encoder, using core elements on each side.
                    filters=args[args.index('videorate')+1:args.index('x264enc')]
                    self.assertIsNone(self.parse_error('fakesrc '+' '.join(filters)+' fakesink'))

    def test_adjacent_caps_reproduce_the_reported_failure(self):
        description='fakesrc ! video/x-raw,framerate=30/1 ! video/x-raw,format=I420 ! fakesink'
        self.assertIn('no element',self.parse_error(description))
