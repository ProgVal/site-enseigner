import unittest

import enseigner.model as model

class EnseignerTestCase(unittest.TestCase):
    def setUp(self):
        super(EnseignerTestCase, self).setUp()
        self.db = model.sqlite3.connect(':memory:', )
        with self.db:
            for table in model.tables:
                table._instances = model.weakref.WeakValueDictionary()
                self.db.execute(table._create_table)
        (self._get_conn, model.get_conn) = (model.get_conn, lambda: self.db)
    def tearDown(self):
        super(EnseignerTestCase, self).setUp()
        model.get_conn = self._get_conn

