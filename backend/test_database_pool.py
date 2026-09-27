import time
import unittest
from types import SimpleNamespace

from sqlalchemy import exc

import database


class FakeConnection:
    def __init__(self, alive=True):
        self.alive = alive
        self.pings = 0

    def ping(self):
        self.pings += 1
        if not self.alive:
            raise OSError("closed by pooler")


class IdlePingTests(unittest.TestCase):
    def test_recently_used_connection_is_not_pinged(self):
        connection = FakeConnection()
        record = SimpleNamespace(info={"checked_in_at": time.monotonic()})
        database._ping_after_idle(connection, record, None)
        self.assertEqual(connection.pings, 0)

    def test_fresh_connection_is_not_pinged(self):
        connection = FakeConnection()
        database._ping_after_idle(connection, SimpleNamespace(info={}), None)
        self.assertEqual(connection.pings, 0)

    def test_idle_connection_is_pinged_and_dead_one_replaced(self):
        idle = SimpleNamespace(info={"checked_in_at": time.monotonic() - database.IDLE_PING_SEC - 1})
        alive = FakeConnection()
        database._ping_after_idle(alive, idle, None)
        self.assertEqual(alive.pings, 1)
        with self.assertRaises(exc.DisconnectionError):
            database._ping_after_idle(FakeConnection(alive=False), idle, None)


if __name__ == "__main__":
    unittest.main()
