import logging
import asyncio
from datetime import datetime, timezone

logger = logging.getLogger("db_fallback")

class MockCursor:
    def __init__(self, data):
        self.data = data
        self.sort_key = None
        self.sort_dir = 1

    def sort(self, key, direction=1):
        if isinstance(key, list) and len(key) > 0:
            # handle list of tuples like sort([("ran_at", -1)])
            self.sort_key = key[0][0]
            self.sort_dir = key[0][1]
        else:
            self.sort_key = key
            self.sort_dir = direction
        return self

    async def to_list(self, limit):
        res = list(self.data)
        if self.sort_key:
            try:
                res.sort(key=lambda x: x.get(self.sort_key) or "", reverse=(self.sort_dir == -1))
            except Exception:
                pass
        return res[:limit]

class MockCollection:
    def __init__(self, name, db):
        self.name = name
        self.db = db
        self._data = []

    async def find_one(self, filter, projection=None, sort=None):
        data = list(self._data)
        if sort:
            # handle sort argument like sort=[("ran_at", -1)]
            key = sort[0][0]
            direction = sort[0][1]
            try:
                data.sort(key=lambda x: x.get(key) or "", reverse=(direction == -1))
            except Exception:
                pass
        
        for doc in data:
            match = True
            for k, v in filter.items():
                if doc.get(k) != v:
                    match = False
                    break
            if match:
                res = dict(doc)
                if projection and "_id" in projection and projection["_id"] == 0:
                    res.pop("_id", None)
                return res
        return None

    async def insert_one(self, document):
        doc = dict(document)
        if "_id" not in doc:
            doc["_id"] = str(len(self._data) + 1)
        self._data.append(doc)
        class InsertResult:
            inserted_id = doc["_id"]
        return InsertResult()

    async def update_one(self, filter, update, upsert=False):
        found = False
        for doc in self._data:
            match = True
            for k, v in filter.items():
                if doc.get(k) != v:
                    match = False
                    break
            if match:
                found = True
                if "$set" in update:
                    doc.update(update["$set"])
                else:
                    doc.update(update)
                break
        
        if not found and upsert:
            doc = dict(filter)
            if "$set" in update:
                doc.update(update["$set"])
            else:
                doc.update(update)
            if "_id" not in doc:
                doc["_id"] = str(len(self._data) + 1)
            self._data.append(doc)

    async def delete_one(self, filter):
        for idx, doc in enumerate(self._data):
            match = True
            for k, v in filter.items():
                if doc.get(k) != v:
                    match = False
                    break
            if match:
                self._data.pop(idx)
                break

    async def delete_many(self, filter):
        if not filter:
            self._data.clear()
            return
        self._data = [doc for doc in self._data if not all(doc.get(k) == v for k, v in filter.items())]

    def find(self, filter=None, projection=None):
        if not filter:
            matched = list(self._data)
        else:
            matched = []
            for doc in self._data:
                match = True
                for k, v in filter.items():
                    if doc.get(k) != v:
                        match = False
                        break
                if match:
                    matched.append(doc)
        
        # apply projection
        projected = []
        for doc in matched:
            res = dict(doc)
            if projection and "_id" in projection and projection["_id"] == 0:
                res.pop("_id", None)
            projected.append(res)
            
        return MockCursor(projected)

class MockDatabase:
    def __init__(self):
        self._collections = {}

    def __getitem__(self, name):
        if name not in self._collections:
            self._collections[name] = MockCollection(name, self)
        return self._collections[name]

    def __getattr__(self, name):
        return self[name]

class DatabaseProxy:
    def __init__(self, mongo_url, db_name):
        self.mongo_url = mongo_url
        self.db_name = db_name
        self.real_client = None
        self.real_db = None
        self.mock_db = MockDatabase()
        self.use_fallback = False
        self._mock_prepopulated = False

    async def _prepopulate_mock_data(self):
        portfolio = self.mock_db.portfolio
        await portfolio.insert_one({
            "_id": "main",
            "balance": 3000.0,
            "initial_balance": 3000.0,
            "currency": "INR",
            "positions": [],
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

    def _get_active_db(self):
        if self.use_fallback:
            if not self._mock_prepopulated:
                self._mock_prepopulated = True
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        asyncio.ensure_future(self._prepopulate_mock_data())
                    else:
                        loop.run_until_complete(self._prepopulate_mock_data())
                except Exception as e:
                    logger.warning(f"Could not prepopulate mock data: {e}")
            return self.mock_db
            
        if self.real_db is None:
            try:
                from motor.motor_asyncio import AsyncIOMotorClient
                self.real_client = AsyncIOMotorClient(self.mongo_url, serverSelectionTimeoutMS=1500)
                self.real_db = self.real_client[self.db_name]
            except Exception as e:
                logger.warning(f"Failed to connect to MongoDB, using memory database: {e}")
                self.use_fallback = True
                return self.mock_db
                
        return self.real_db

    def __getitem__(self, name):
        return CollectionProxy(name, self)

    def __getattr__(self, name):
        return self[name]

    def close(self):
        if self.real_client:
            self.real_client.close()

class CollectionProxy:
    def __init__(self, name, db_proxy):
        self.name = name
        self.db_proxy = db_proxy

    def _get_collection(self):
        db = self.db_proxy._get_active_db()
        return db[self.name]

    async def find_one(self, *args, **kwargs):
        try:
            return await self._get_collection().find_one(*args, **kwargs)
        except Exception as e:
            if not self.db_proxy.use_fallback:
                logger.warning(f"MongoDB operation failed, falling back to memory database: {e}")
                self.db_proxy.use_fallback = True
                return await self._get_collection().find_one(*args, **kwargs)
            raise

    async def insert_one(self, *args, **kwargs):
        try:
            return await self._get_collection().insert_one(*args, **kwargs)
        except Exception as e:
            if not self.db_proxy.use_fallback:
                logger.warning(f"MongoDB operation failed, falling back to memory database: {e}")
                self.db_proxy.use_fallback = True
                return await self._get_collection().insert_one(*args, **kwargs)
            raise

    async def update_one(self, *args, **kwargs):
        try:
            return await self._get_collection().update_one(*args, **kwargs)
        except Exception as e:
            if not self.db_proxy.use_fallback:
                logger.warning(f"MongoDB operation failed, falling back to memory database: {e}")
                self.db_proxy.use_fallback = True
                return await self._get_collection().update_one(*args, **kwargs)
            raise

    async def delete_one(self, *args, **kwargs):
        try:
            return await self._get_collection().delete_one(*args, **kwargs)
        except Exception as e:
            if not self.db_proxy.use_fallback:
                logger.warning(f"MongoDB operation failed, falling back to memory database: {e}")
                self.db_proxy.use_fallback = True
                return await self._get_collection().delete_one(*args, **kwargs)
            raise

    async def delete_many(self, *args, **kwargs):
        try:
            return await self._get_collection().delete_many(*args, **kwargs)
        except Exception as e:
            if not self.db_proxy.use_fallback:
                logger.warning(f"MongoDB operation failed, falling back to memory database: {e}")
                self.db_proxy.use_fallback = True
                return await self._get_collection().delete_many(*args, **kwargs)
            raise

    def find(self, *args, **kwargs):
        # returns a cursor (which is not awaited immediately)
        # we return a CursorProxy
        return CursorProxy(self, args, kwargs)

class CursorProxy:
    def __init__(self, col_proxy, args, kwargs):
        self.col_proxy = col_proxy
        self.args = args
        self.kwargs = kwargs
        self.sort_args = None
        
    def sort(self, *args, **kwargs):
        self.sort_args = (args, kwargs)
        return self

    async def to_list(self, *args, **kwargs):
        try:
            col = self.col_proxy._get_collection()
            cursor = col.find(*self.args, **self.kwargs)
            if self.sort_args:
                cursor = cursor.sort(*self.sort_args[0], **self.sort_args[1])
            return await cursor.to_list(*args, **kwargs)
        except Exception as e:
            if not self.col_proxy.db_proxy.use_fallback:
                logger.warning(f"MongoDB operation failed, falling back to memory database: {e}")
                self.col_proxy.db_proxy.use_fallback = True
                # retry with mock
                col = self.col_proxy._get_collection()
                cursor = col.find(*self.args, **self.kwargs)
                if self.sort_args:
                    cursor = cursor.sort(*self.sort_args[0], **self.sort_args[1])
                return await cursor.to_list(*args, **kwargs)
            raise
