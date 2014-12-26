from testutils import EnseignerTestCase

import enseigner.model as model

class ModelTestCase(EnseignerTestCase):
    def testSingleton(self):
        t1 = model.Tutor.create('foo', 'bar', False)
        self.assertRaises(model.Duplicate, model.Tutor.create, 'foo', 'bar', False)
        self.assertIs(t1, model.Tutor.get('foo'))
        self.assertRaises(AssertionError, model.Tutor, t1.uid, 'foo', 'bar', False)
        self.assertRaises(model.NotFound, model.Tutor.get, 'foobar')
        del model.Tutor._instances[t1.uid]
        self.assertEqual(t1.uid, model.Tutor.get('foo').uid)
        self.assertEqual(t1.uid, model.Tutor.get(t1.uid).uid)
        self.assertRaises(ValueError, model.Tutor.get, ('foo',))

    def testRepr(self):
        t1 = model.Tutor.create('foo', 'bar')
        self.assertEqual(repr(t1),
                "<enseigner.model.Tutor(uid=1, email='foo', "
                "password_hash='%s', phone_number=None, is_admin=False, "
                "is_active=True, comment=None)>" %
                model.password_hash(t1.uid, 'bar'))

class TutorTestCase(EnseignerTestCase):
    def testGetTutors(self):
        t1 = model.Tutor.create('foo', 'bar', False)
        self.assertEqual(list(model.Tutor.all()), [t1])

    def testCheckPassword(self):
        t1 = model.Tutor.create('foo', 'bar', False)
        model.Tutor.create('foo2', 'bar2', False)
        t2 = model.Tutor.get('foo2')
        self.assertIs(t1, model.Tutor.check_password('foo', 'bar'))
        self.assertIs(None, model.Tutor.check_password('foo', 'bar2'))
        self.assertIs(t2, model.Tutor.check_password('foo2', 'bar2'))
        self.assertIs(None, model.Tutor.check_password('foo2', 'bar'))

class StudentTestCase(EnseignerTestCase):
    def testGetStudents(self):
        s1 = model.Student.create('foo', 'bar', False, False, '')
        s2 = model.Student.create('foo2', 'bar2', False, False, '')
        self.assertRaises(model.Duplicate, model.Student.create, 'foo2', 'bar', True, False, 'baz')
        self.assertEqual(list(model.Student.all()), [s1, s2])
        self.assertIs(model.Student.get(s2.uid), s2)
        self.assertRaises(ValueError, model.Student.get, s2.emails)

class TregTestCase(EnseignerTestCase):
    def testCheckForeignKeys(self):
        self.assertRaises(model.ForeignKeyNotMapped,
                model.TutorRegistration.create, 10, 10, 3, None)
        t1 = model.Tutor.create('foo', 'bar', False)
        self.assertRaises(model.ForeignKeyNotMapped,
                model.TutorRegistration.create, 10, t1, 3, None)
        s1 = model.Session.create('foo', 'bar')
        self.assertRaises(model.ForeignKeyNotMapped,
                model.TutorRegistration.create, s1, 10, 3, None)
        model.TutorRegistration.create(s1, t1, 3, None)

    def testAllInSession(self):
        s1 = model.Session.create('foo', 'bar')
        s2 = model.Session.create('foo2', 'bar2')
        t1 = model.Tutor.create('foo', 'bar', False)
        t2 = model.Tutor.create('foo2', 'bar', False)
        t3 = model.Tutor.create('foo3', 'bar', False)
        tr1 = model.TutorRegistration.create(s1, t1, 3, None)
        tr2 = model.TutorRegistration.create(s1, t3, 3, None)
        tr3 = model.TutorRegistration.create(s2, t3, 3, None)
        self.assertEqual(set(model.TutorRegistration.all_in_session(s1)),
                         {tr1, tr2})
        self.assertEqual(set(model.TutorRegistration.all_in_session(s2)),
                         {tr3})

    def testGetFind(self):
        s1 = model.Session.create('foo', 'bar')
        s2 = model.Session.create('foo2', 'bar2')
        t1 = model.Tutor.create('foo', 'bar', False)
        t2 = model.Tutor.create('foo2', 'bar', False)
        t3 = model.Tutor.create('foo3', 'bar', False)
        tr1 = model.TutorRegistration.create(s1, t1, 3, None)
        tr2 = model.TutorRegistration.create(s1, t3, 3, None)
        tr3 = model.TutorRegistration.create(s2, t3, 3, None)
        self.assertIs(model.TutorRegistration.find(s1, t3), tr2)
        self.assertIs(model.TutorRegistration.find(s2, t3), tr3)
        self.assertIs(model.TutorRegistration.find(s2.sid, t3.uid), tr3)
        self.assertRaises(model.NotFound, model.TutorRegistration.find, s2, t2)
        self.assertRaises(model.ForeignKeyNotMapped, model.TutorRegistration.find, 50, t2)
        self.assertRaises(model.ForeignKeyNotMapped, model.TutorRegistration.find, s2, 50)
        self.assertIs(model.TutorRegistration.get(tr2.trid), tr2)
        self.assertRaises(model.NotFound, model.TutorRegistration.get, 100)

    def testSubjects(self):
        s1 = model.Session.create('foo', 'bar')
        s2 = model.Session.create('foo2', 'bar2')
        t1 = model.Tutor.create('foo', 'bar', False)
        t2 = model.Tutor.create('foo2', 'bar', False)
        t3 = model.Tutor.create('foo3', 'bar', False)
        tr1 = model.TutorRegistration.create(s1, t1, 3, None)
        tr2 = model.TutorRegistration.create(s1, t3, 3, None)
        tr3 = model.TutorRegistration.create(s2, t3, 3, None)
        sub1 = model.Subject.create('foo', False)
        sub2 = model.Subject.create('bar', False)
        sub3 = model.Subject.create('baz', False)
        ts1 = model.TutorRegistrationSubject.create(tr1, sub2, 1)
        ts2 = model.TutorRegistrationSubject.create(tr1.trid, sub3, 2)
        ts3 = model.TutorRegistrationSubject.create(tr2, sub2.sid, 3)
        self.assertEqual(set(model.TutorRegistrationSubject.all_of_treg(tr1)),
                {ts1, ts2})
        self.assertEqual(set(model.TutorRegistrationSubject.all_of_treg(tr2)),
                {ts3})

class SregTestCase(EnseignerTestCase):
    def testGetFindAll(self):
        s1 = model.Session.create('foo', 'bar')
        s2 = model.Session.create('foo2', 'bar2')
        st1 = model.Student.create('foo', 'bar', False, False, '')
        st2 = model.Student.create('foo2', 'bar2', False, False, '')
        st3 = model.Student.create('foo3', 'bar3', False, False, '')
        sub1 = model.Subject.create('foo', False)
        sub2 = model.Subject.create('bar', False)
        sub3 = model.Subject.create('baz', False)
        sr1 = model.StudentRegistration.create(s1, st1, sub1, 1, None)
        sr2 = model.StudentRegistration.create(s1, st3, sub3.sid, 1,None)
        sr3 = model.StudentRegistration.create(s2, st3.uid, sub2, 1, None)
        sr4 = model.StudentRegistration.create(s2.sid, st1, sub2, 1, None)
        self.assertRaises(model.Duplicate,
                model.StudentRegistration.create, s1, st1, sub2, 2, None)
        self.assertEqual(set(model.StudentRegistration.all_in_session(s1)),
                {sr1, sr2})
        self.assertEqual(set(model.StudentRegistration.all_in_session(s1.sid)),
                {sr1, sr2})
        self.assertIs(model.StudentRegistration.find(s1, st3), sr2)
        self.assertIs(model.StudentRegistration.find(s1.sid, st3), sr2)
        self.assertIs(model.StudentRegistration.find(s1, st3.uid), sr2)
        self.assertRaises(model.ForeignKeyNotMapped,
                model.StudentRegistration.find, 10, 10)
        self.assertRaises(model.NotFound,
                model.StudentRegistration.find, s2, st2)
        self.assertIs(model.StudentRegistration.get(sr3.srid), sr3)

    def testGet(self):
        self.assertRaises(ValueError, model.StudentRegistration.get, 'foo')

class MiscTestCase(EnseignerTestCase):
    def testSession(self):
        s1 = model.Session.create('foo', 'bar')
        s2 = model.Session.create('foo2', 'bar2')
        self.assertEqual(set(model.Session.all()), {s1, s2})

    def testSubject(self):
        self.assertRaises(ValueError, model.Subject.get, 'foo')
        sub1 = model.Subject.create('foo', False)
        sub2 = model.Subject.create('bar', True)
        sub3 = model.Subject.create('baz', False)
        self.assertEqual(set(model.Subject.all_permanent()), {sub1, sub3})
        self.assertEqual(set(model.Subject.all()), {sub1, sub2, sub3})

    def testSessionSubject(self):
        s1 = model.Session.create('foo', 'bar')
        s2 = model.Session.create('foo2', 'bar2')
        s3 = model.Session.create('foo3', 'bar3')
        sub1 = model.Subject.create('foo', True)
        sub2 = model.Subject.create('bar', True)
        sub3 = model.Subject.create('baz', True)
        sub4 = model.Subject.create('qux', False)
        sub5 = model.Subject.create('quux', False)
        ss1 = model.SessionSubject.create_for_session(s1, [sub1, sub3])
        self.assertRaises(model.Duplicate,
                model.SessionSubject.create_for_session, s2, [sub2, sub2])
        ss2 = model.SessionSubject.create_for_session(s2, [sub2, sub3])
        ss2 = model.SessionSubject.create_for_session(s3.sid, [sub2.sid, sub3.sid])
        self.assertEqual(set(model.SessionSubject.all_subjects_for_session(s1)),
                {sub1, sub3, sub4, sub5})
        self.assertEqual(set(model.SessionSubject.all_subjects_for_session(s2.sid)),
                {sub2, sub3, sub4, sub5})
        self.assertEqual(set(model.SessionSubject.all_subjects_for_session(s3)),
                {sub2, sub3, sub4, sub5})
