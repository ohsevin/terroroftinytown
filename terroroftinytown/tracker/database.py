# encoding=utf-8
import redis
import rom.util


class Database(object):
    def __init__(self, host='localhost', port=6379, db=0):
        self._connection = redis.StrictRedis(
            host=host, port=port, db=db, decode_responses=True
        )
        rom.util.set_connection_settings(host=host, port=port, db=db)
