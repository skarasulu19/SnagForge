import asyncio
import unittest
from dbus_next import Message,MessageType,Variant
from portal import Portal,ROOT,Cancelled


class RequestBus:
    unique_name=':1.55'
    def __init__(self,response=0,alternate=False,cleanup_failure=False):
        self.response=response;self.alternate=alternate;self.cleanup_failure=cleanup_failure
        self.handler=None;self.closed=[]
    def add_message_handler(self,handler):self.handler=handler
    def remove_message_handler(self,handler):self.handler=None
    async def call(self,msg):
        if msg.member in ('AddMatch','RemoveMatch'):
            if msg.member=='RemoveMatch' and self.cleanup_failure:raise RuntimeError('bus disappeared during cleanup')
            return Message(message_type=MessageType.METHOD_RETURN,reply_serial=1)
        if msg.member=='Close':
            self.closed.append(msg.path)
            return Message(message_type=MessageType.ERROR,reply_serial=1,error_name='org.freedesktop.DBus.Error.UnknownMethod',signature='s',body=['Object does not exist'])
        token=msg.body[-1]['handle_token'].value
        handle=ROOT+'/request/1_55/'+('alternate_handle' if self.alternate else token)
        if self.response is not None:
            # Response arrives BEFORE the method reply with its actual handle.
            self.handler(Message(message_type=MessageType.SIGNAL,path=handle,
                interface='org.freedesktop.portal.Request',member='Response',signature='ua{sv}',
                body=[self.response,{'uri':Variant('s','file:///tmp/test.png')}]))
        return Message(message_type=MessageType.METHOD_RETURN,reply_serial=1,signature='o',body=[handle])


class RequestLifecycleTests(unittest.TestCase):
    def test_returned_handle_is_used_even_with_early_response(self):
        async def run():
            portal=Portal();portal.bus=RequestBus(alternate=True)
            self.assertEqual(await portal.screenshot(),'file:///tmp/test.png')
            self.assertIsNone(portal.bus.handler)
        asyncio.run(run())
    def test_disappeared_request_does_not_mask_timeout(self):
        async def run():
            portal=Portal();portal.bus=RequestBus(response=None);portal.request_timeout=.01
            with self.assertRaisesRegex(RuntimeError,'Screenshot.Screenshot timed out'):
                await portal.screenshot()
            self.assertEqual(len(portal.bus.closed),1);self.assertIsNone(portal.bus.handler)
        asyncio.run(run())
    def test_task_cancellation_closes_request_and_removes_handler(self):
        async def run():
            portal=Portal();portal.bus=RequestBus(response=None,alternate=True)
            task=asyncio.create_task(portal.screenshot());await asyncio.sleep(.01);task.cancel()
            with self.assertRaises(asyncio.CancelledError):await task
            self.assertEqual(portal.bus.closed,[ROOT+'/request/1_55/alternate_handle'])
            self.assertIsNone(portal.bus.handler)
        asyncio.run(run())
    def test_match_cleanup_failure_preserves_success(self):
        async def run():
            portal=Portal();portal.bus=RequestBus(cleanup_failure=True)
            self.assertEqual(await portal.screenshot(),'file:///tmp/test.png')
        asyncio.run(run())
    def test_failed_response_identifies_the_request_stage(self):
        async def run():
            portal=Portal();portal.bus=RequestBus(response=2)
            with self.assertRaisesRegex(RuntimeError,r'ScreenCast.Start failed \(desktop response 2\)'):
                await portal.request('org.freedesktop.portal.ScreenCast','Start','osa{sv}',['/session',''],{})
        asyncio.run(run())
