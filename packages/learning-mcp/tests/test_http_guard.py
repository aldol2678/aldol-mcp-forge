import asyncio,unittest
from server import BearerGuard

class BearerTests(unittest.TestCase):
    def test_auth(self):
        async def app(scope,receive,send):
            await send({"type":"http.response.start","status":200,"headers":[]})
            await send({"type":"http.response.body","body":b"OK"})
        with self.assertRaises(ValueError): BearerGuard(app,"too-short")
        wrap=BearerGuard(app,"x"*32)
        async def check(headers):
            events=[]
            async def send(e): events.append(e)
            async def receive(): return {"type":"http.request","body":b"","more_body":False}
            await wrap({"type":"http","headers":headers},receive,send)
            return events[0]["status"]
        self.assertEqual(asyncio.run(check([])),401)
        owner=(b"authorization",b"Bearer "+b"x"*32)
        self.assertEqual(asyncio.run(check([owner])),200)
        self.assertEqual(asyncio.run(check([owner,(b"origin",b"https://example.com")])),403)
