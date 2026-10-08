import asyncio

from starlette.responses import JSONResponse
from app.core.middleware import ExternalReadLimitMiddleware


def test_broker_read_saturation_preserves_other_requests():
    async def exercise():
        entered = asyncio.Event()
        release = asyncio.Event()
        async def app(scope, receive, send):
            if scope['path'] == '/api/kis-chart/candles':
                entered.set()
                await release.wait()
            await JSONResponse({'ok': True})(scope, receive, send)
        middleware = ExternalReadLimitMiddleware(app, limit=1)
        async def request(path, method='GET'):
            messages = []
            async def receive(): return {'type': 'http.request', 'body': b'', 'more_body': False}
            async def send(message): messages.append(message)
            await middleware({'type': 'http', 'path': path, 'method': method}, receive, send)
            return messages[0]['status']
        first = asyncio.create_task(request('/api/kis-chart/candles'))
        await entered.wait()
        assert await request('/api/kis-chart/candles') == 503
        assert await request('/api/member/me') == 200
        assert await request('/api/alpaca-test/paper/order-flow-test', 'POST') == 200
        release.set()
        assert await first == 200
        assert middleware.slots._value == 1
    asyncio.run(exercise())


def test_cancelled_read_releases_slot():
    async def exercise():
        entered = asyncio.Event()
        async def app(scope, receive, send):
            entered.set()
            await asyncio.Event().wait()
        middleware = ExternalReadLimitMiddleware(app, limit=1)
        task = asyncio.create_task(middleware({'type': 'http', 'method': 'GET', 'path': '/api/kis-chart/candles'}, None, None))
        await entered.wait()
        task.cancel()
        try: await task
        except asyncio.CancelledError: pass
        assert middleware.slots._value == 1
    asyncio.run(exercise())
