#!/usr/bin/env python2
import enseigner.model as model

conn = model.get_conn()
with conn:
    for table in model.tables:
        conn.execute(table._create_table)

