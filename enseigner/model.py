from future_builtins import map, filter
import os
import hashlib
import sqlite3
import weakref

class NotFound(Exception):
    pass
class Duplicate(Exception):
    pass
class Contradictory(Exception):
    pass

tables = []
def register(cls):
    tables.append(cls)
    return cls


def password_hash(tutor_email, password):
    salt = os.environ.get('ENSEIGNER_SECRET_SALT', '')
    assert len(salt) >= 20, 'Salt is not long enough'
    return hashlib.sha512('%s|%s|%s' % (salt, tutor_email, password)).hexdigest()


def get_conn(): # pragma: no cover
    return sqlite3.connect('database.sqlite3')

@register
class Tutor(object):
    _create_table = '''CREATE TABLE tutors (
        tutor_id INTEGER PRIMARY KEY,
        tutor_email TEXT UNIQUE,
        tutor_password_hash TEXT,
        tutor_is_admin BOOLEAN
        )'''
    _instances = weakref.WeakValueDictionary()
    _fields = ('uid', 'email', 'password_hash', 'is_admin')
    def __init__(self, uid, email, password_hash, is_admin):
        if uid in self._instances:
            assert self._instances[uid] is self
        else:
            self._instances[uid] = self
        self.uid = uid
        self.email = email
        self.password_hash = password_hash
        self.is_admin = is_admin

    def __repr__(self):
        return '<enseigner.model.Tutor(%s)>' % ', '.join(
                ['%s=%r' % (x, getattr(self, x)) for x in self._fields])

    @classmethod
    def create(cls, email, password, is_admin):
        conn = get_conn()
        c = conn.cursor()
        hash_ = password_hash(email, password)
        try:
            c.execute('''INSERT INTO tutors
                         (tutor_email, tutor_password_hash, tutor_is_admin)
                         VALUES (?, ?, ?)''',
                      (email, hash_, is_admin))
            r = c.lastrowid
        except sqlite3.IntegrityError:
            raise Duplicate()
        else:
            conn.commit()
        finally:
            c.close()
        return Tutor(r, email, hash_, is_admin)

        
    @classmethod
    def get(cls, tutor_email):
        conn = get_conn()
        c = conn.cursor()
        try:
            c.execute('''SELECT * FROM tutors 
                         WHERE tutor_email=?''',
                      (tutor_email,))
            r = c.fetchone()
        finally:
            c.close()
        if not r:
            raise NotFound()
        if r[0] in cls._instances:
            return cls._instances[r[0]]
        else:
            instance = cls(*r)
            cls._instances[r[0]] = instance
            return instance 

    @classmethod
    def get_tutors(cls):
        conn = get_conn()
        c = conn.cursor()
        try:
            c.execute('''SELECT * FROM tutors''')
            r = c.fetchall()
        finally:
            c.close()
        return map(lambda x:cls._instances.get(x[0], None) or cls(*x), r)


    @classmethod
    def check_password(cls, tutor_email, password):
        conn = get_conn()
        c = conn.cursor()
        try:
            c.execute('''SELECT * FROM tutors 
                         WHERE tutor_email=? AND tutor_password_hash=?''',
                      (tutor_email, password_hash(tutor_email, password)))
            r = c.fetchone()
        finally:
            c.close()
        if r:
            return cls._instances.get(r[0], None) or cls(*r)
        else:
            return None

