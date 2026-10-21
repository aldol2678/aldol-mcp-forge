import json, unittest
from ui_core import core
from ui_core.http_server import PrivateEndpoint

class Operations(unittest.TestCase):
    def test_http_fail_closed(self):
        for token in ('','short'):
            with self.assertRaises(ValueError): PrivateEndpoint(None,token)
    def test_deep_json_is_validation_failure(self):
        self.assertFalse(core.validate('['*10000+'0'+']'*10000)['valid'])
    def test_markup_exceptions_reject_bad_shapes(self):
        for ex in ('{}','null','[1]','[{}]'):
            with self.assertRaises(ValueError): core.review_markup('<h1>저장</h1>',ex)
