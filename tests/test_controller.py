from testutils import EnseignerTestCase

import enseigner.model as model
import enseigner.controller as controller

class ControllerTestCase(EnseignerTestCase):
    def testCreateSession(self):
        sub1 = model.Subject.create('foo', False)
        sub2 = model.Subject.create('bar', True)
        sub3 = model.Subject.create('baz', False)
        s1 = controller.create_session('24/12/2014 22:55', ['qux', 'quux'])
        s2 = controller.create_session('24/12/2014 22:55', ['corge'])
        self.assertEqual({x.name for x in model.Subject.all()},
                {'foo', 'bar', 'baz', 'qux', 'quux', 'corge'})
        self.assertEqual({x.name for x in model.SessionSubject.all_subjects_for_session(s1)},
                {'foo', 'bar', 'baz', 'qux', 'quux'})
        self.assertEqual({x.name for x in model.SessionSubject.all_subjects_for_session(s2)},
                {'foo', 'bar', 'baz', 'corge'})

    def testTutorSubscription(self):
        sub1 = model.Subject.create('foo', False)
        sub2 = model.Subject.create('bar', True)
        sub3 = model.Subject.create('baz', False)
        t1 = model.Tutor.create('foo', 'bar', 'baz', False)
        t2 = model.Tutor.create('foo2', 'bar', 'baz', False)
        s1 = controller.create_session('26/12/2014 20:50', ['qux', 'quux'])
        s2 = controller.create_session('26/12/2014 20:50', ['corge'])
        sub4 = [x for x in model.SessionSubject.all_subjects_for_session(s1) if x.name == 'qux'][0]
        h = controller.hash_subscription_params(s1.sid, 'tutor', t1.uid)
        self.assertEqual(controller.get_tutor_form_data(str(s1.sid), str(t1.uid), h),
                ('foo', 'bar', set(), 0, ''))
        self.assertRaises(controller.WrongHash,
                controller.get_tutor_form_data, str(s1.sid), str(t1.uid), '')
        controller.set_tutor_form_data(str(s1.sid), str(t1.uid), h, [str(sub1.sid), str(sub4.sid)], 3, 'qux')
        (email, name, subjects, group_size, comment) = controller.get_tutor_form_data(str(s1.sid), str(t1.uid), h)
        self.assertEqual(email, 'foo')
        self.assertEqual(name, 'bar')
        self.assertEqual({x.name for x in subjects}, {'foo', 'qux'})
        self.assertEqual(group_size, 3)
        self.assertEqual(comment, 'qux')
        self.assertRaises(controller.WrongHash,
                controller.get_tutor_form_data, str(s1.sid), str(t1.uid), '')

        controller.set_tutor_form_data(str(s1.sid), str(t1.uid), h, [str(sub1.sid), str(sub3.sid)], 4, 'quux')
        (email, name, subjects, group_size, comment) = controller.get_tutor_form_data(str(s1.sid), str(t1.uid), h)
        self.assertEqual(email, 'foo')
        self.assertEqual(name, 'bar')
        self.assertEqual({x.name for x in subjects}, {'foo', 'baz'})
        self.assertEqual(group_size, 4)
        self.assertEqual(comment, 'quux')
