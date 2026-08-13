import unittest
import os
import tempfile
from db import init_db, create_call_record, update_call_outcome, get_call_analytics

class TestCallAnalytics(unittest.TestCase):
    def setUp(self):
        # Setup temporary database file
        self.db_fd, self.db_path = tempfile.mkstemp()
        init_db(self.db_path)

    def tearDown(self):
        # Close and remove temp database file
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def test_call_lifecycle(self):
        # 1. Initially counts should be 0
        stats = get_call_analytics(self.db_path)
        self.assertEqual(stats["total"], 0)
        self.assertEqual(stats["successful"], 0)
        self.assertEqual(stats["failed"], 0)
        self.assertEqual(len(stats["recent_calls"]), 0)

        # 2. Add an active call
        create_call_record("session_1", "Ramesh Pawar", db_path=self.db_path)
        stats = get_call_analytics(self.db_path)
        self.assertEqual(stats["total"], 1)
        self.assertEqual(stats["successful"], 0)
        self.assertEqual(stats["failed"], 1) # Default is failed until outcome is success

        # 3. Update outcome to success
        update_call_outcome("session_1", "success", "Fetched weather", "Ramesh Pawar", db_path=self.db_path)
        stats = get_call_analytics(self.db_path)
        self.assertEqual(stats["total"], 1)
        self.assertEqual(stats["successful"], 1)
        self.assertEqual(stats["failed"], 0)

        # 4. Add another call that remains failed
        create_call_record("session_2", "Suresh Kumar", db_path=self.db_path)
        update_call_outcome("session_2", "failed", "Caller disconnected", "Suresh Kumar", db_path=self.db_path)
        stats = get_call_analytics(self.db_path)
        self.assertEqual(stats["total"], 2)
        self.assertEqual(stats["successful"], 1)
        self.assertEqual(stats["failed"], 1)

if __name__ == '__main__':
    unittest.main()
