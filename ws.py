import asyncio
from websockets import WebSocketServerProtocol
from websockets.server import serve
import http
import http.cookies

app_secret = "25ca83c71412e4cb81691ffe"

# Based off of https://github.com/python-websockets/websockets/blob/1bf9d1d766c80da4887240737266926f173fbcef/experiments/authentication/app.py#L36
def get_cookie(raw, key):
    cookie = http.cookies.SimpleCookie(raw)
    morsel = cookie.get(key)

    if morsel is not None:
        return decode_flask_cookie(app_secret, morsel.value)

class Auth(WebSocketServerProtocol):
    async def process_request(self, path, headers):
        session = get_cookie(headers.get("Cookie", ""), "session")

        if session is None or "token" not in session:
            return http.HTTPStatus.UNAUTHORIZED, [], b"missing token\n"

        self.token = session["token"]

# From https://gist.github.com/babldev/502364a3f7c9bafaa6db
def decode_flask_cookie(secret_key, cookie_str):
    import hashlib
    from itsdangerous import URLSafeTimedSerializer
    from flask.sessions import TaggedJSONSerializer
    salt = 'cookie-session'
    serializer = TaggedJSONSerializer()
    signer_kwargs = {
        'key_derivation': 'hmac',
        'digest_method': hashlib.sha1
    }
    s = URLSafeTimedSerializer(secret_key, salt=salt, serializer=serializer, signer_kwargs=signer_kwargs)
    return s.loads(cookie_str)

async def handler(ws):
    await ws.send(f"Hello, client: {ws.token}")

    async for msg in ws:
        await ws.send(f"Client, received {msg!r}")

async def main():
    async with serve(handler, host="localhost", port=3000, create_protocol=Auth):
        await asyncio.Future()

asyncio.run(main())