from testutils import EnseignerTestCase

import enseigner.model as model

class TutorTestCase(EnseignerTestCase):
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
        t1 = model.Tutor.create('foo', 'bar', False)
        self.assertEqual(repr(t1),
                "<enseigner.model.Tutor(uid=1, email='foo', "
                "password_hash='%s', is_admin=False)>" %
                model.password_hash('foo', 'bar'))

    def testGetTutors(self):
        t1 = model.Tutor.create('foo', 'bar', False)
        self.assertEqual(list(model.Tutor.get_tutors()), [t1])

    def testCheckPassword(self):
        t1 = model.Tutor.create('foo', 'bar', False)
        model.Tutor.create('foo2', 'bar2', False)
        t2 = model.Tutor.get('foo2')
        self.assertIs(t1, model.Tutor.check_password('foo', 'bar'))
        self.assertIs(None, model.Tutor.check_password('foo', 'bar2'))
        self.assertIs(t2, model.Tutor.check_password('foo2', 'bar2'))
        self.assertIs(None, model.Tutor.check_password('foo2', 'bar'))

