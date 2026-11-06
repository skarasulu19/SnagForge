"""Desktop portal client. Capture permission stays with the desktop compositor."""
import asyncio
import logging
import uuid
from dbus_next import Message, MessageType, Variant
from dbus_next.aio import MessageBus

DEST = 'org.freedesktop.portal.Desktop'
ROOT = '/org/freedesktop/portal/desktop'

class Cancelled(Exception):
    pass

class Portal:
    async def connect(self):
        self.bus = await MessageBus(negotiate_unix_fd=True).connect()
        return self

    async def call(self, interface, member, signature='', body=None, path=ROOT):
        reply = await self.bus.call(Message(destination=DEST, path=path,
            interface=interface, member=member, signature=signature, body=body or []))
        if reply.message_type == MessageType.ERROR:
            raise RuntimeError(f'{reply.error_name}: {reply.body}')
        return reply

    request_timeout=180
    cleanup_timeout=2

    async def close_request(self,path):
        # Requests may disappear before a timeout/cancel reaches cleanup.
        try:
            await asyncio.wait_for(self.call('org.freedesktop.portal.Request','Close',path=path),self.cleanup_timeout)
        except Exception:
            pass

    async def request(self, interface, member, signature, body, options):
        stage=interface.rsplit('.',1)[-1]+'.'+member
        token='snagforge_'+uuid.uuid4().hex
        options=dict(options,handle_token=Variant('s',token))
        sender=self.bus.unique_name[1:].replace('.','_')
        path=f'{ROOT}/request/{sender}/{token}'
        actual=None;buffered={}
        future=asyncio.get_running_loop().create_future()
        def receive(msg):
            if (msg.message_type!=MessageType.SIGNAL or
                msg.interface!='org.freedesktop.portal.Request' or msg.member!='Response'):
                return
            if actual is None:
                if msg.path and msg.path.startswith(ROOT+'/request/'):
                    buffered[msg.path]=msg.body
            elif msg.path==actual and not future.done():
                future.set_result(msg.body)
        self.bus.add_message_handler(receive)
        # Subscribe before calling, including replies whose returned handle
        # differs from the predicted handle. Correlate only the returned path.
        rule=(f"type='signal',sender='{DEST}',interface='org.freedesktop.portal.Request',"
              f"member='Response',path_namespace='{ROOT}/request'")
        matched=False
        logging.info('Portal %s: requesting',stage)
        try:
            match=await self.bus.call(Message(destination='org.freedesktop.DBus',
                path='/org/freedesktop/DBus',interface='org.freedesktop.DBus',
                member='AddMatch',signature='s',body=[rule]))
            if match.message_type==MessageType.ERROR:raise RuntimeError(str(match.body))
            matched=True
            reply=await asyncio.wait_for(self.call(interface,member,signature,body+[options]),self.request_timeout)
            returned=reply.body[0] if reply.body else None
            if not isinstance(returned,str) or not returned.startswith(ROOT+'/request/'):
                raise RuntimeError(stage+' returned an invalid request handle.')
            path=actual=returned
            if actual in buffered and not future.done():future.set_result(buffered[actual])
            buffered.clear()
            code,result=await asyncio.wait_for(future,self.request_timeout)
            if code==1:raise Cancelled('Capture cancelled')
            if code:raise RuntimeError(f'{stage} failed (desktop response {code}).')
            logging.info('Portal %s: completed',stage)
            return {k:v.value for k,v in result.items()}
        except asyncio.TimeoutError:
            await self.close_request(path)
            raise RuntimeError(f'{stage} timed out waiting for Ubuntu. Cancel any open capture picker and try again.') from None
        except asyncio.CancelledError:
            await self.close_request(path)
            logging.info('Portal %s: cancelled',stage)
            raise
        finally:
            self.bus.remove_message_handler(receive)
            if matched:
                try:
                    await asyncio.wait_for(self.bus.call(Message(destination='org.freedesktop.DBus',
                        path='/org/freedesktop/DBus',interface='org.freedesktop.DBus',
                        member='RemoveMatch',signature='s',body=[rule])),self.cleanup_timeout)
                except Exception:
                    pass

    async def screenshot(self):
        return (await self.request('org.freedesktop.portal.Screenshot', 'Screenshot',
            'sa{sv}', [''], {'interactive': Variant('b', True)}))['uri']

    async def screencast(self):
        interface = 'org.freedesktop.portal.ScreenCast'
        result = await self.request(interface, 'CreateSession', 'a{sv}', [],
            {'session_handle_token': Variant('s', 'session_' + uuid.uuid4().hex)})
        self.session = result['session_handle']
        await self.request(interface, 'SelectSources', 'oa{sv}', [self.session],
            {'types': Variant('u', 3), 'multiple': Variant('b', False),
             'cursor_mode': Variant('u', 2)})
        result = await self.request(interface, 'Start', 'osa{sv}', [self.session, ''], {})
        return result['streams'][0][0]

    async def remote(self):
        reply = await self.call('org.freedesktop.portal.ScreenCast', 'OpenPipeWireRemote',
                                'oa{sv}', [self.session, {}])
        return reply.unix_fds[reply.body[0]]

    async def close(self):
        """Release the portal session and bus without failing application shutdown.

        GNOME may remove a ScreenCast session itself when capture is cancelled,
        stopped, or its PipeWire stream ends.  Calling ``Close`` after that is a
        normal race and must not escape a worker thread as an exception.
        """
        bus = getattr(self, 'bus', None)
        session = getattr(self, 'session', None)
        self.session = None
        try:
            if bus and session:
                try:
                    await asyncio.wait_for(self.call('org.freedesktop.portal.Session','Close',path=session),self.cleanup_timeout)
                except Exception:
                    # Session.Close is cleanup only.  The compositor is allowed
                    # to destroy the object first, and a disconnected session
                    # bus is equally safe to regard as already closed.
                    pass
        finally:
            if bus:
                try:
                    bus.disconnect()
                except Exception:
                    pass
            self.bus = None

