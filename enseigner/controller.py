import hashlib
import datetime
import collections

import model
from config import config

class WrongHash(Exception):
    pass
def hash_subscription_params(session_id, type_, user_id):
    salt = config['secret_key']
    assert len(salt) >= 20, 'Secret is not long enough'
    assert type_ in ('tutor', 'student'), type_
    return hashlib.sha512('%s|%s|%s|%s' % (salt, type_, session_id, user_id))\
            .hexdigest()
def check_hash(type_):
    def decorator(f):
        def newf(session_id, user_id, hash_, *args):
            if hash_subscription_params(session_id, type_, user_id) != hash_:
                raise WrongHash()
            return f(session_id, user_id, *args)
        return newf
    return decorator

def parse_human_date(date):
    return datetime.datetime.strptime(date, "%d/%m/%Y %H:%M")

def create_session(date, exceptional_subjects_names):
    date = parse_human_date(date)
    session = model.Session.create(date, '', False, False)
    subjects = list(model.Subject.all_permanent())
    for subject in exceptional_subjects_names:
        subjects.append(model.Subject.create(subject, True))
    model.SessionSubject.create_for_session(session, subjects)
    return session

TutorForm = collections.namedtuple('TutorForm',
        'email name subjects group_size comment')
@check_hash('tutor')
def get_tutor_form_data(session, tutor):
    tutor = model.Tutor.get(int(tutor))
    try:
        treg = model.TutorRegistration.find(int(session), tutor)
        subjects = (model.Subject.get(x.sid)
                    for x in model.TutorRegistrationSubject.all_of_treg(treg))
        group_size = treg.group_size
        comment = treg.comment
    except model.NotFound:
        subjects = set()
        group_size = 0
        comment = ''
    return TutorForm(tutor.email, tutor.name, subjects, group_size, comment)

@check_hash('tutor')
def set_tutor_form_data(session, tutor, subjects, group_size, comment):
    try:
        treg = model.TutorRegistration.find(int(session), int(tutor))
        treg.update(group_size, comment)
    except model.NotFound:
        treg = model.TutorRegistration.create(int(session), int(tutor), group_size, comment)
    # TODO: handle multiple preferences
    model.TutorRegistrationSubject.set_for_treg(treg,
            ((model.Subject.get(int(x)), 1) for x in subjects))

@check_hash('student')
def get_student_form_data(session, student):
    try:
        return model.StudentRegistration.find(int(session), int(student))
    except model.NotFound:
        return None
