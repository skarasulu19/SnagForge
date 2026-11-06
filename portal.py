"""Desktop portal client. Capture permission stays with the desktop compositor."""
import asyncio
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

    async def request(self, interface, member, signature, body, options):
        token = 'snagforge_' + uuid.uuid4().hex
        options = dict(options, handle_token=Variant('s', token))
        sender = self.bus.unique_name[1:].replace('.', '_')
        path = f'{ROOT}/request/{sender}/{token}'
        future = asyncio.get_running_loop().create_future()
        def receive(msg):
            if (msg.message_type == MessageType.SIGNAL and msg.path == path
                and msg.interface == 'org.freedesktop.portal.Request' and msg.member == 'Response'):
                if not future.done():
                    future.set_result(msg.body)
        self.bus.add_message_handler(receive)
        rule = f"type='signal',interface='org.freedesktop.portal.Request',path='{path}'"
        try:
            match = await self.bus.call(Message(destination='org.freedesktop.DBus',
                path='/org/freedesktop/DBus', interface='org.freedesktop.DBus',
                member='AddMatch', signature='s', body=[rule]))
            if match.message_type == MessageType.ERROR:
                raise RuntimeError(str(match.body))
            await self.call(interface, member, signature, body + [options])
            try:
                code, result = await asyncio.wait_for(future, 180)
            except asyncio.TimeoutError:
                await self.call('org.freedesktop.portal.Request', 'Close', path=path)
                raise RuntimeError('Capture picker timed out. Try again.')
            if code == 1:
                raise Cancelled('Capture cancelled')
            if code:
                raise RuntimeError(f'Desktop rejected the capture (response {code}).')
            return {k: v.value for k, v in result.items()}
        finally:
            self.bus.remove_message_handler(receive)
            await self.bus.call(Message(destination='org.freedesktop.DBus',
                path='/org/freedesktop/DBus', interface='org.freedesktop.DBus',
                member='RemoveMatch', signature='s', body=[rule]))

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
        try:
            if getattr(self, 'session', None):
                await self.call('org.freedesktop.portal.Session', 'Close', path=self.session)
        finally:
            self.bus.disconnect()
