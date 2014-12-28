from future_builtins import map, filter
import os
import hashlib
import sqlite3
import weakref
import datetime

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
            else:
                raise AttributeError('%r has not attribute %r' % (self, name))

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
            return {cls._instances.get(cls.make_id(x), None) or cls(*x)
                    for x in r}

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
        tutor_name TEXT,
        tutor_password_hash TEXT,
        tutor_phone_number TEXT,
        tutor_is_admin BOOLEAN,
        tutor_is_active BOOLEAN,
        tutor_comment TEXT
        )'''
    _instances = weakref.WeakValueDictionary()
    _fields = ('uid', 'email', 'name', 'password_hash', 'phone_number', 'is_admin', 'is_active', 'comment')

    @classmethod
    def create(cls, email, name, password, phone_number=None, is_admin=False, is_active=True, comment=None):
        t = cls._insert_one('''tutor_email, tutor_name, tutor_password_hash, tutor_phone_number,
                               tutor_is_admin, tutor_is_active, tutor_comment''',
                            (email, name, None, phone_number, is_admin, is_active, comment))
        t.password_hash = password_hash(t.uid, password)
        conn = get_conn()
        c = conn.cursor()
        try:
            c.execute('''UPDATE tutors SET tutor_password_hash=?
                         WHERE tutor_id=?''', (t.password_hash, t.uid))
            conn.commit()
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
    def all_active(cls):
        return cls._get_many('''SELECT * FROM tutors
                                WHERE tutor_is_active=1''')


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

    @classmethod
    def all_active_not_blacklisted(cls):
        return cls._get_many('''SELECT * FROM students
                                WHERE student_is_active=1
                                AND student_blacklisted=0''')

@register
class Session(SingleKeyModel):
    _table = 'sessions'
    _create_table = '''CREATE TABLE sessions (
        session_id INTEGER PRIMARY KEY,
        session_date DATETIME,
        session_managers TEXT,
        session_form_comment_students TEXT,
        session_form_comment_tutors TEXT,
        session_emailed_students BOOLEAN,
        session_emailed_tutors BOOLEAN,
        session_is_open BOOLEAN
        )'''
    _instances = weakref.WeakValueDictionary()
    _fields = ('sid', 'date', 'managers',
            'session_form_comment_students', 'session_form_comment_tutors',
            'emailed_students', 'emailed_tutors', 'is_open')

    @property
    def date(self):
        return datetime.datetime.strptime(self._attributes['date'],
                '%Y-%m-%d %H:%M:%S')

    @classmethod
    def create(cls, date, managers,
            form_comment_students='', form_comment_tutors='',
            emailed_students=False, emailed_tutors=False, is_open=True):
        return cls._insert_one('''session_date, session_managers,
                                  session_form_comment_students,
                                  session_form_comment_tutors,
                                  session_emailed_students,
                                  session_emailed_tutors,
                                  session_is_open''',
                               (date, managers, form_comment_students,
                                form_comment_tutors, emailed_students,
                                emailed_tutors,
                                is_open))

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

    @property
    def nb_students(self):
        conn = get_conn()
        c = conn.cursor()
        try:
            c.execute('''SELECT COUNT() FROM student_registrations
                         WHERE session_id=?''', (self.sid,))
            r = c.fetchone()[0]
        finally:
            c.close()
        return r

    @property
    def nb_tutors(self):
        conn = get_conn()
        c = conn.cursor()
        try:
            c.execute('''SELECT COUNT() FROM tutor_registrations
                         WHERE session_id=?''', (self.sid,))
            r = c.fetchone()[0]
        finally:
            c.close()
        return r

    def set_emailed_tutors(self):
        conn = get_conn()
        conn.execute('''UPDATE sessions SET
                        session_emailed_tutors=1
                        WHERE session_id=?''',
                     (self.sid,))
        conn.commit()
        self.emailed_tutors = 1

    def set_emailed_students(self):
        conn = get_conn()
        conn.execute('''UPDATE sessions SET
                        session_emailed_students=1
                        WHERE session_id=?''',
                     (self.sid,))
        conn.commit()
        self.emailed_students = 1


@register
class TutorRegistration(SingleKeyModel):
    _table = 'tutor_registrations'
    _create_table = '''CREATE TABLE tutor_registrations (
        treg_id INTEGER PRIMARY KEY,
        session_id INTEGER,
        treg_tutor_id INTEGER,
        treg_group_size INTEGER,
        treg_comment TEXT,
        FOREIGN KEY (session_id) REFERENCES sessions(session_id),
        FOREIGN KEY (treg_tutor_id) REFERENCES tutors(tutor_id),
        UNIQUE (session_id, treg_tutor_id)
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
        return cls._insert_one('''session_id, treg_tutor_id,
                                  treg_group_size, treg_comment''',
                               (session, tutor) + args)

    @classmethod
    def all_in_session(cls, session):
        if isinstance(session, Session):
            session = session.sid
        assert isinstance(session, int), session
        return cls._get_many('''SELECT * FROM tutor_registrations
                                WHERE session_id=?''', (session,))

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
                             WHERE session_id=? AND treg_tutor_id=?''',
                          (session, tutor))
        r = list(r)
        if not r:
            raise NotFound()
        else:
            assert len(r) == 1
            return r[0]

    def update(self, group_size, comment):
        conn = get_conn()
        conn.execute('''UPDATE tutor_registrations SET
                        treg_group_size=?, treg_comment=?
                        WHERE treg_id=?''',
                     (group_size, comment, self.trid,))
        conn.commit()
        self.group_size = group_size
        self.comment = comment

@register
class Subject(SingleKeyModel):
    _table = 'subjects'
    _create_table = '''CREATE TABLE subjects (
        subject_id INTEGER PRIMARY KEY,
        subject_name TEXT,
        subject_is_exceptional BOOLEAN,
        subject_color TEXT
        )'''
    _instances = weakref.WeakValueDictionary()
    _fields = ('sid', 'name', 'color', 'is_exceptional')

    @classmethod
    def create(cls, name, is_exceptional=False, color='#000000'):
        return cls._insert_one('''subject_name,
                                  subject_is_exceptional,
                                  subject_color''',
                               (name, is_exceptional, color))

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
        ss_is_open INTEGER,
        FOREIGN KEY (session_id) REFERENCES sessions(session_id),
        FOREIGN KEY (subject_id) REFERENCES subjects(subject_id),
        UNIQUE (session_id, subject_id)
        )'''
    _instances = weakref.WeakValueDictionary()
    _fields = ('ssid', 'seid', 'suid', 'is_open')

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
        l = list(map(lambda x:(session, x, True), subjects))
        return cls._insert_many('session_id, subject_id, ss_is_open', l)

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

    @classmethod
    def set_for_treg(cls, treg, l):
        if isinstance(treg, TutorRegistration):
            treg = treg.trid
        else:
            cls._check_exists(TutorRegistration, treg)
        assert isinstance(treg, int), treg
        assert hasattr(l, '__iter__'), l
        conn = get_conn()
        c = conn.cursor()
        try:
            c.execute('''DELETE FROM tutor_registrations_subject
                         WHERE tregs_treg_id=?''', (treg,))
            for (subject, preference) in l:
                if isinstance(subject, Subject):
                    subject = subject.sid
                else:
                    cls._check_exists(Subject, subject)
                c.execute('''INSERT INTO tutor_registrations_subject
                             (tregs_treg_id, tregs_subject_id, tregs_preference)
                             VALUES (?, ?, ?);''',
                          (treg, subject, preference))
        except sqlite3.IntegrityError:
            conn.rollback()
            raise Duplicate()
        else:
            conn.commit()
        finally:
            c.close()

@register
class StudentRegistration(SingleKeyModel):
    _table = 'student_registrations'
    _create_table = '''CREATE TABLE student_registrations (
        sreg_id INTEGER PRIMARY KEY,
        session_id INTEGER,
        student_id INTEGER,
        subject_id INTEGER,
        sreg_friends INTEGER,
        sreg_comment TEXT,
        FOREIGN KEY (session_id) REFERENCES sessions(session_id),
        FOREIGN KEY (student_id) REFERENCES students(student_id),
        FOREIGN KEY (subject_id) REFERENCES subjects(subject_id),
        UNIQUE (session_id, student_id)
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
        return cls._insert_one('''session_id, student_id,
                                  subject_id, sreg_friends, sreg_comment''',
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
                                WHERE session_id=?''', (session,))

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
                             WHERE session_id=? AND student_id=?''',
                          (session, student))
        r = list(r)
        if not r:
            raise NotFound()
        else:
            assert len(r) == 1, r
            return r[0]

    def update(self, subject, friends, comment):
        if isinstance(subject, Subject):
            subject = subject.sid
        else:
            cls._check_exists(Subject, subject)
        assert isinstance(friends, int), friends
        assert isinstance(comment, str), comment
        assert isinstance(subject, int), subject
        conn = get_conn()
        conn.execute('''UPDATE student_registrations SET
                        subject_id=?, sreg_friends=?, sreg_comment=?
                        WHERE sreg_id=?''',
                     (subject, friends, comment, self.srid,))
        conn.commit()
        self.subject = subject
        self.friends = friends
        self.comment = comment

@register
class Mail(SingleKeyModel):
    _table = 'mails'
    _create_table = '''CREATE TABLE mails (
        mail_id INTEGER PRIMARY KEY,
        mail_recipient TEXT,
        mail_subject TEXT,
        mail_content TEXT,
        mail_sent BOOLEAN
        )'''
    _instances = weakref.WeakValueDictionary()
    _fields = ('mid', 'recipient', 'subject', 'content', 'sent')

    @classmethod
    def create(cls, recipient, content, sent=False):
        return cls._insert_one('''mail_recipient, mail_subject, mail_content, mail_sent''',
                               (recipient, content, sent))

    @classmethod
    def create_many(cls, rows):
        rows = [(x[0], x[1], x[2], x[3] if len(x) > 3 else False) for x in rows]
        return cls._insert_many('''mail_recipient, mail_subject, mail_content, mail_sent''',
                                rows)

    @classmethod
    def get(cls, mid):
        conn = get_conn()
        c = conn.cursor()
        try:
            c.execute('''SELECT * FROM mails
                         WHERE mail_id=?''',
                      (mid,))
            r = c.fetchone()
        finally:
            c.close()
        return cls._get_or_create(r)

    @classmethod
    def all_unsent(cls):
        return cls._get_many('''SELECT * FROM mails WHERE mail_sent=0''')

    def set_sent(self):
        conn = get_conn()
        conn.execute('''UPDATE mails SET mail_sent=1
                        WHERE mail_id=?''',
                     (self.mid,))
        conn.commit()
        self.sent = True
