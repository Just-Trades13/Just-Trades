import asyncio
import websockets
import json
import ssl
import certifi
import aiohttp
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TradovateAPI:
    def __init__(self, username=None, password=None, api_key=None, api_secret=None,
                 api_endpoint="https://api.tradovate.com/v1",
                 websocket_url="wss://md.tradovate.com/v1/websocket",
                 demo=False):
        self.username = username
        self.password = password
        self.api_key = api_key
        self.api_secret = api_secret
        self.api_endpoint = api_endpoint
        self.websocket_url = websocket_url
        self.demo = demo
        self.wstoken = None
        self.userid = None
        self.accounts = []
        self.websocket = None
        self.session = None # For aiohttp client session
        self.ssl_context = ssl.create_default_context(cafile=certifi.where())

    async def _send_ws_message(self, message_type, payload):
        if not self.websocket or not self.websocket.open:
            logger.error("WebSocket not connected.")
            return None
        message = json.dumps([message_type, payload])
        await self.websocket.send(message)
        response = await self.websocket.recv()
        return json.loads(response)

    async def _http_request(self, method, path, data=None, headers=None):
        url = f"{self.api_endpoint}{path}"
        if not self.session:
            self.session = aiohttp.ClientSession()
        
        _headers = {"Content-Type": "application/json"}
        if self.wstoken:
            _headers["Authorization"] = f"Bearer {self.wstoken}"
        if headers:
            _headers.update(headers)

        async with self.session.request(method, url, json=data, headers=_headers, ssl=self.ssl_context) as response:
            response.raise_for_status()
            return await response.json()

    async def login(self):
        if self.username and self.password:
            logger.info(f"Attempting login with credentials for user: {self.username}")
            path = "/auth/accessTokenRequest"
            data = {
                "name": self.username,
                "password": self.password,
                "appId": "Just.Trade",
                "appVersion": "1.0",
                "cid": "Just.Trade",
                "deviceId": "Just.Trade-Device",
                "deviceOs": "Linux",
                "mediaCode": "Just.Trade"
            }
            try:
                response = await self._http_request("POST", path, data=data)
                self.wstoken = response.get("accessToken")
                self.userid = response.get("userId")
                logger.info("Login successful with credentials.")
                return True
            except aiohttp.ClientResponseError as e:
                logger.error(f"HTTP error during credentials login: {e.status} - {e.message}")
                return False
            except Exception as e:
                logger.error(f"Error during credentials login: {e}")
                return False
        elif self.api_key and self.api_secret:
            logger.info("Attempting login with API key and secret.")
            path = "/auth/accessTokenRequest"
            data = {
                "name": self.api_key,
                "password": self.api_secret, # Tradovate uses password field for API secret
                "appId": "Just.Trade",
                "appVersion": "1.0",
                "cid": "Just.Trade",
                "deviceId": "Just.Trade-Device",
                "deviceOs": "Linux",
                "mediaCode": "Just.Trade"
            }
            try:
                response = await self._http_request("POST", path, data=data)
                self.wstoken = response.get("accessToken")
                self.userid = response.get("userId")
                logger.info("Login successful with API key.")
                return True
            except aiohttp.ClientResponseError as e:
                logger.error(f"HTTP error during API key login: {e.status} - {e.message}")
                return False
            except Exception as e:
                logger.error(f"Error during API key login: {e}")
                return False
        else:
            logger.error("No credentials or API key/secret provided for login.")
            return False

    async def connect_websocket(self):
        if not self.wstoken:
            logger.error("Cannot connect WebSocket, no access token available. Please login first.")
            return False
        try:
            self.websocket = await websockets.connect(self.websocket_url, ssl=self.ssl_context)
            logger.info("WebSocket connected.")
            # Send authorization message
            auth_message = json.dumps(["authorize", {"token": self.wstoken}])
            await self.websocket.send(auth_message)
            response = await self.websocket.recv()
            auth_result = json.loads(response)
            if auth_result[0] == "ok":
                logger.info("WebSocket authorized.")
                return True
            else:
                logger.error(f"WebSocket authorization failed: {auth_result}")
                return False
        except Exception as e:
            logger.error(f"Error connecting or authorizing WebSocket: {e}")
            return False

    async def get_accounts(self):
        if not self.wstoken:
            logger.error("Not logged in. Cannot fetch accounts.")
            return []
        try:
            response = await self._http_request("GET", "/account/list")
            self.accounts = response
            logger.info(f"Fetched {len(self.accounts)} accounts.")
            return self.accounts
        except Exception as e:
            logger.error(f"Error fetching accounts: {e}")
            return []

    async def place_order(self, account_id, symbol, order_type, quantity, price=None, stop_price=None):
        # This is a simplified example. Real order placement requires more parameters.
        if not self.wstoken:
            logger.error("Not logged in. Cannot place order.")
            return None
        try:
            path = "/order/placeOrder"
            data = {
                "accountId": account_id,
                "symbol": symbol,
                "orderType": order_type, # e.g., 'Market', 'Limit', 'Stop'
                "quantity": quantity,
                "action": "Buy", # or "Sell"
                # Add more parameters as needed for specific order types
            }
            if price:
                data["price"] = price
            if stop_price:
                data["stopPrice"] = stop_price

            response = await self._http_request("POST", path, data=data)
            logger.info(f"Order placed: {response}")
            return response
        except Exception as e:
            logger.error(f"Error placing order: {e}")
            return None

    async def get_market_data(self, symbol):
        if not self.websocket or not self.websocket.open:
            logger.error("WebSocket not connected for market data.")
            return None
        try:
            # Example: Subscribe to quote for a symbol
            # This is a simplified example, actual Tradovate market data subscription is more complex
            # and involves sending specific messages to the WebSocket.
            # For now, we'll just simulate a response.
            logger.info(f"Subscribing to market data for {symbol}...")
            await asyncio.sleep(1) # Simulate subscription delay
            return {"symbol": symbol, "lastPrice": 123.45, "bid": 123.40, "ask": 123.50}
        except Exception as e:
            logger.error(f"Error getting market data: {e}")
            return None

    async def close(self):
        if self.websocket:
            await self.websocket.close()
            logger.info("WebSocket closed.")
        if self.session:
            await self.session.close()
            logger.info("HTTP session closed.")