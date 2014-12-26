import hashlib
import datetime

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

@check_hash('tutor')
def get_tutor_subjects(session, tutor):
    try:
        treg = model.TutorRegistration.find(int(session), int(tutor))
        return (model.Subject.get(x.sid)
                for x in model.TutorRegistrationSubject.all_of_treg(treg))
    except model.NotFound:
        return []

@check_hash('tutor')
def set_tutor_subjects(session, tutor, subjects, group_size, comments):
    try:
        treg = model.TutorRegistration.find(int(session), int(tutor))
        # TODO: handle change of group size and comment
    except model.NotFound:
        treg = model.TutorRegistration.create(int(session), int(tutor), group_size, comments)
    # TODO: handle multiple preferences
    model.TutorRegistrationSubject.set_for_treg(treg,
            ((model.Subject.get(int(x)), 1) for x in subjects))
