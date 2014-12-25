from future_builtins import map, filter
import os
import hashlib
import sqlite3
import weakref

from config import config

class NotFound(Exception):
    pass
class ForeignKeyNotMapped(Exception):
    pass
class Duplicate(Exception):
    pass
class Contradictory(Exception):
    pass

tables = []
def register(cls):
    tables.append(cls)
    return cls


def password_hash(tutor_id, password):
    salt = config['password_salt']
    assert len(salt) >= 20, 'Salt is not long enough'
    return hashlib.sha512('%s|%d|%s' % (salt, tutor_id, password)).hexdigest()


def get_conn(): # pragma: no cover
    return sqlite3.connect('database.sqlite3')

def _model(nb_keys):
    class Model(object):
        @staticmethod
        def make_id(args):
            return tuple(args[0:nb_keys])
        def __init__(self, *args):
            id_ = self.make_id(args)
            if id_ in self._instances:
                assert self._instances[id_] is self
            else:
                self._instances[id_] = self
                self._attributes = dict(zip(self._fields, args))

        def __repr__(self):
            return '<enseigner.model.%s(%s)>' % (self.__class__.__name__,
                    ', '.join(['%s=%r' % (x, getattr(self, x))
                               for x in self._fields]))

        def __getattr__(self, name):
            if name in self._attributes:
                return self._attributes[name]

        @classmethod
        def _check_exists(cls, cls2, key):
            try:
                cls2.get(key)
            except NotFound:
                raise ForeignKeyNotMapped()

        @classmethod
        def _get_or_create(cls, data):
            if not data:
                raise NotFound()
            id_ = cls.make_id(data)
            if id_ in cls._instances:
                return cls._instances[id_]
            else:
                instance = cls(*data)
                cls._instances[id_] = instance
                return instance 

        @classmethod
        def _fetch_many(cls, request, args=()):
            conn = get_conn()
            c = conn.cursor()
            try:
                c.execute(request, args)
                r = c.fetchall()
            finally:
                c.close()
            return r

        @classmethod
        def _get_many(cls, request, args=()):
            r = cls._fetch_many(request, args)
            return map(lambda x:cls._instances.get(cls.make_id(x), None) or 
                                cls(*x), r)

    Model.__name__ = 'Model(%d)' % nb_keys
    return Model

class SingleKeyModel(_model(1)):
    @classmethod
    def make_id(self, args):
        return args[0]

    @classmethod
    def _insert_one(cls, cols, args):
        conn = get_conn()
        c = conn.cursor()
        try:
            c.execute('INSERT INTO %s (%s) VALUES (%s)' %
                      (cls._table, cols, ', '.join('?'*len(args))), args)
            r = c.lastrowid
        except sqlite3.IntegrityError:
            raise Duplicate()
        else:
            conn.commit()
        finally:
            c.close()
        return cls(r, *args)

    @classmethod
    def _insert_many(cls, cols, l):
        conn = get_conn()
        c = conn.cursor()
        r = []
        try:
            for args in l:
                c.execute('INSERT INTO %s (%s) VALUES (%s);' % \
                          (cls._table, cols, ', '.join('?'*len(args))),
                          args)
                r.append((c.lastrowid, args))
        except sqlite3.IntegrityError:
            conn.rollback()
            raise Duplicate()
        else:
            conn.commit()
        finally:
            c.close()
        return list(cls(x, *args) for (x, args) in r)

DoubleKeyModel = _model(2)
TripleKeyModel = _model(3)

@register
class Tutor(SingleKeyModel):
    _table = 'tutors'
    _create_table = '''CREATE TABLE tutors (
        tutor_id INTEGER PRIMARY KEY,
        tutor_email TEXT UNIQUE,
        tutor_password_hash TEXT,
        tutor_phone_number TEXT,
        tutor_is_admin BOOLEAN,
        tutor_is_active BOOLEAN,
        tutor_comment TEXT
        )'''
    _instances = weakref.WeakValueDictionary()
    _fields = ('uid', 'email', 'password_hash', 'phone_number', 'is_admin', 'is_active', 'comment')

    @classmethod
    def create(cls, email, password, phone_number=None, is_admin=False, is_active=True, comment=None):
        t = cls._insert_one('''tutor_email, tutor_password_hash, tutor_phone_number,
                               tutor_is_admin, tutor_is_active, tutor_comment''',
                            (email, None, phone_number, is_admin, is_active, comment))
        t.password_hash = password_hash(t.uid, password)
        conn = get_conn()
        c = conn.cursor()
        try:
            c.execute('''UPDATE tutors SET tutor_password_hash=?
                         WHERE tutor_id=?''', (t.password_hash, t.uid))
        finally:
            c.close()

        return t

        
    @classmethod
    def get(cls, email_or_id):
        conn = get_conn()
        c = conn.cursor()
        try:
            if isinstance(email_or_id, (str, unicode)):
                c.execute('''SELECT * FROM tutors
                             WHERE tutor_email=?''',
                          (email_or_id,))
            elif isinstance(email_or_id, int):
                c.execute('''SELECT * FROM tutors
                             WHERE tutor_id=?''',
                          (email_or_id,))
            else:
                raise ValueError('email_or_id should be str or int, not %r' %
                        email_or_id)
            r = c.fetchone()
        finally:
            c.close()
        return cls._get_or_create(r)

    @classmethod
    def all(cls):
        return cls._get_many('''SELECT * FROM tutors''')


    @classmethod
    def check_password(cls, tutor_email, password):
        conn = get_conn()
        c = conn.cursor()
        c.execute('SELECT tutor_id FROM tutors WHERE tutor_email=?',
                (tutor_email,))
        r = c.fetchone()
        if not r:
            return None
        tutor_id = r[0]
        try:
            c.execute('''SELECT * FROM tutors 
                         WHERE tutor_id=? AND tutor_password_hash=?''',
                      (tutor_id, password_hash(tutor_id, password)))
            r = c.fetchone()
        finally:
            c.close()
        if r:
            return cls._instances.get(r[0], None) or cls(*r)
        else:
            return None


@register
class Student(SingleKeyModel):
    _table = 'students'
    _create_table = '''CREATE TABLE students (
        student_id INTEGER PRIMARY KEY,
        student_emails TEXT,
        student_name TEXT UNIQUE,
        student_phone_number TEXT,
        student_is_active BOOLEAN,
        student_blacklisted BOOLEAN,
        student_comment TEXT
        )'''
    _instances = weakref.WeakValueDictionary()
    _fields = ('uid', 'emails', 'name', 'is_active', 'blacklisted', 'comment')

    @classmethod
    def create(cls, emails, name, phone_number=None, is_active=True, blacklisted=False, comment=None):
        return cls._insert_one('''student_emails, student_name, student_phone_number,
                                  student_is_active, student_blacklisted, student_comment''',
                               (emails, name, phone_number, is_active, blacklisted, comment))

        
    @classmethod
    def get(cls, uid):
        conn = get_conn()
        c = conn.cursor()
        try:
            if not isinstance(uid, int):
                raise ValueError('id should be or int, not %r' %
                        uid)
            c.execute('''SELECT * FROM students
                         WHERE student_id=?''',
                      (uid,))
            r = c.fetchone()
        finally:
            c.close()
        return cls._get_or_create(r)

    @classmethod
    def all(cls):
        return cls._get_many('''SELECT * FROM students''')

@register
class Session(SingleKeyModel):
    _table = 'sessions'
    _create_table = '''CREATE TABLE sessions (
        session_id INTEGER PRIMARY KEY,
        session_date DATETIME,
        session_managers TEXT,
        session_emailed_students BOOLEAN,
        session_emailed_tutors BOOLEAN
        )'''
    _instances = weakref.WeakValueDictionary()
    _fields = ('sid', 'date', 'managers', 'emailed_students', 'emailed_tutors')

    @classmethod
    def create(cls, date, managers, emailed_students=False, emailed_tutors=False):
        return cls._insert_one('''session_date, session_managers,
                                  session_emailed_students,
                                  session_emailed_tutors''',
                               (date, managers, emailed_students, emailed_tutors))

    @classmethod
    def get(cls, sid):
        assert isinstance(sid, int)
        conn = get_conn()
        c = conn.cursor()
        try:
            c.execute('''SELECT * FROM sessions
                         WHERE session_id=?''',
                      (sid,))
            r = c.fetchone()
        finally:
            c.close()
        return cls._get_or_create(r)

    @classmethod
    def all(cls):
        return cls._get_many('''SELECT * FROM sessions''')


@register
class TutorRegistration(SingleKeyModel):
    _table = 'tutor_registrations'
    _create_table = '''CREATE TABLE tutor_registrations (
        treg_id INTEGER PRIMARY KEY,
        treg_session_id INTEGER,
        treg_tutor_id INTEGER,
        treg_group_size INTEGER,
        treg_comment TEXT,
        FOREIGN KEY (treg_session_id) REFERENCES sessions(session_id),
        FOREIGN KEY (treg_tutor_id) REFERENCES tutors(tutor_id),
        UNIQUE (treg_session_id, treg_tutor_id)
        )'''
    _instances = weakref.WeakValueDictionary()
    _fields = ('trid', 'sid', 'uid', 'group_size', 'comment')

    @classmethod
    def create(cls, session, tutor, *args):
        if isinstance(session, Session):
            session = session.sid
        else:
            cls._check_exists(Session, session)
        if isinstance(tutor, Tutor):
            tutor = tutor.uid
        else:
            cls._check_exists(Tutor, tutor)
        return cls._insert_one('''treg_session_id, treg_tutor_id,
                                  treg_group_size, treg_comment''',
                               (session, tutor) + args)

    @classmethod
    def all_in_session(cls, session):
        if isinstance(session, Session):
            session = session.sid
        assert isinstance(session, int), session
        return cls._get_many('''SELECT * FROM tutor_registrations
                                WHERE treg_session_id=?''', (session,))

    @classmethod
    def get(cls, trid):
        conn = get_conn()
        c = conn.cursor()
        try:
            c.execute('''SELECT * FROM tutor_registrations
                         WHERE treg_id=?''',
                      (trid,))
            r = c.fetchone()
        finally:
            c.close()
        return cls._get_or_create(r)

    @classmethod
    def find(cls, session, tutor):
        if isinstance(session, Session):
            session = session.sid
        else:
            cls._check_exists(Session, session)
        if isinstance(tutor, Tutor):
            tutor = tutor.uid
        else:
            cls._check_exists(Tutor, tutor)
        r = cls._get_many('''SELECT * FROM tutor_registrations
                             WHERE treg_session_id=? AND treg_tutor_id=?''',
                          (session, tutor))
        r = list(r)
        if not r:
            raise NotFound()
        else:
            assert len(r) == 1
            return r[0]

@register
class Subject(SingleKeyModel):
    _table = 'subjects'
    _create_table = '''CREATE TABLE subjects (
        subject_id INTEGER PRIMARY KEY,
        subject_name TEXT,
        subject_is_exceptional BOOLEAN
        )'''
    _instances = weakref.WeakValueDictionary()
    _fields = ('sid', 'name', 'is_exceptional')

    @classmethod
    def create(cls, *args):
        return cls._insert_one('subject_name, subject_is_exceptional', args)
        
    @classmethod
    def get(cls, sid):
        conn = get_conn()
        c = conn.cursor()
        try:
            if not isinstance(sid, int):
                raise ValueError('id should be or int, not %r' %
                        sid)
            c.execute('''SELECT * FROM subjects
                         WHERE subject_id=?''',
                      (sid,))
            r = c.fetchone()
        finally:
            c.close()
        return cls._get_or_create(r)

    @classmethod
    def all_permanent(cls):
        return cls._get_many('''SELECT * FROM subjects
                                WHERE subject_is_exceptional=0''')

    @classmethod
    def all(cls):
        return cls._get_many('''SELECT * FROM subjects''')

@register
class SessionSubject(SingleKeyModel):
    _table = 'session_subjects'
    _create_table = '''CREATE TABLE session_subjects (
        ss_id INTEGER PRIMARY KEY,
        session_id INTEGER,
        subject_id INTEGER,
        FOREIGN KEY (session_id) REFERENCES sessions(session_id),
        FOREIGN KEY (subject_id) REFERENCES subjects(subject_id),
        UNIQUE (session_id, subject_id)
        )'''
    _instances = weakref.WeakValueDictionary()
    _fields = ('ssid', 'seid', 'suid')

    @classmethod
    def create_for_session(cls, session, subjects):
        if isinstance(session, Session):
            session = session.sid
        else:
            cls._check_exists(Session, session)
        for subject in subjects:
            if not isinstance(subject, Subject):
                cls._check_exists(Subject, subject)
        subjects = (s.sid if isinstance(s, Subject) else s for s in subjects)
        l = list(map(lambda x:(session, x), subjects))
        return cls._insert_many('session_id, subject_id', l)

    @classmethod
    def all_subjects_for_session(cls, session):
        if isinstance(session, Session):
            session = session.sid
        else:
            cls._check_exists(Session, session)
        return Subject._get_many('''SELECT * FROM subjects
                                    LEFT JOIN session_subjects USING (subject_id)
                                    WHERE session_id IS NULL OR session_id=?''',
                                   (session,))


@register
class TutorRegistrationSubject(SingleKeyModel):
    _table = 'tutor_registrations_subject'
    _create_table = '''CREATE TABLE tutor_registrations_subject (
        tregs_id INTEGER PRIMARY KEY,
        tregs_treg_id INTEGER,
        tregs_subject_id INTEGER,
        tregs_preference INTEGER,
        FOREIGN KEY (tregs_treg_id) REFERENCES tutor_registrations(treg_id),
        FOREIGN KEY (tregs_subject_id) REFERENCES subjects(subject_id),
        UNIQUE (tregs_treg_id, tregs_subject_id)
        )'''
    _instances = weakref.WeakValueDictionary()
    _fields = ('id', 'trid', 'sid', 'preference')

    @classmethod
    def create(cls, treg, subject, pref):
        if isinstance(treg, TutorRegistration):
            treg = treg.trid
        else:
            cls._check_exists(TutorRegistration, treg)
        if isinstance(subject, Subject):
            subject = subject.sid
        else:
            cls._check_exists(Subject, subject)
        return cls._insert_one('''tregs_treg_id, tregs_subject_id,
                                  tregs_preference''', (treg, subject, pref))

    @classmethod
    def all_of_treg(cls, treg):
        if isinstance(treg, TutorRegistration):
            treg = treg.trid
        assert isinstance(treg, int), treg
        return cls._get_many('''SELECT * FROM tutor_registrations_subject
                                WHERE tregs_treg_id=?''', (treg,))

@register
class StudentRegistration(SingleKeyModel):
    _table = 'student_registrations'
    _create_table = '''CREATE TABLE student_registrations (
        sreg_id INTEGER PRIMARY KEY,
        sreg_session_id INTEGER,
        sreg_student_id INTEGER,
        sreg_subject_id INTEGER,
        sreg_friends INTEGER,
        sreg_comment TEXT,
        FOREIGN KEY (sreg_session_id) REFERENCES sessions(session_id),
        FOREIGN KEY (sreg_student_id) REFERENCES students(student_id),
        FOREIGN KEY (sreg_subject_id) REFERENCES subjects(subject_id),
        UNIQUE (sreg_session_id, sreg_student_id)
        )'''
    _fields = ('srid', 'seid', 'stid', 'suid', 'friends', 'comment')

    @classmethod
    def create(cls, session, student, subject, *args):
        if isinstance(session, Session):
            session = session.sid
        else:
            cls._check_exists(Session, session)
        if isinstance(student, Student):
            student = student.uid
        else:
            cls._check_exists(Student, student)
        if isinstance(subject, Subject):
            subject = subject.sid
        else:
            cls._check_exists(Subject, subject)
        assert isinstance(session, int), session
        assert isinstance(student, int), student
        assert isinstance(subject, int), subject
        return cls._insert_one('''sreg_session_id, sreg_student_id,
                                  sreg_subject_id, sreg_friends, sreg_comment''',
                               (session, student, subject) + args)
        
    @classmethod
    def get(cls, sid):
        conn = get_conn()
        c = conn.cursor()
        try:
            if not isinstance(sid, int):
                raise ValueError('id should be or int, not %r' %
                        sid)
            c.execute('''SELECT * FROM student_registrations
                         WHERE sreg_id=?''',
                      (sid,))
            r = c.fetchone()
        finally:
            c.close()
        return cls._get_or_create(r)

    @classmethod
    def all_in_session(cls, session):
        if isinstance(session, Session):
            session = session.sid
        assert isinstance(session, int), session
        return cls._get_many('''SELECT * FROM student_registrations
                                WHERE sreg_session_id=?''', (session,))

    @classmethod
    def find(cls, session, student):
        if isinstance(session, Session):
            session = session.sid
        else:
            assert isinstance(session, int), session
            cls._check_exists(Session, session)
        if isinstance(student, Student):
            student = student.uid
        else:
            assert isinstance(student, int), student
            cls._check_exists(Student, student)
        r = cls._get_many('''SELECT * FROM student_registrations
                             WHERE sreg_session_id=? AND sreg_student_id=?''',
                          (session, student))
        r = list(r)
        if not r:
            raise NotFound()
        else:
            assert len(r) == 1, r
            return r[0]
