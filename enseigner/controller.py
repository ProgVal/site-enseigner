import csv
import string
import smtplib
import hashlib
import datetime
import operator
import collections

import model
import emails
from config import config

TutorForm = collections.namedtuple('TutorForm',
        'tutor subjects group_size comment')
StudentForm = collections.namedtuple('StudentForm',
        'student subject friends comment')

class WrongHash(Exception):
    pass
def hash_subscription_params(session_id, type_, user_id):
    salt = config['secret_key']
    assert len(salt) >= 20, 'Secret is not long enough'
    assert type_ in ('tutor', 'student'), type_
    return hashlib.sha256('%s|%s|%s|%s' % (salt, type_, session_id, user_id))\
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

def get_tutor_registration_list_rows(session):
    Row = collections.namedtuple('Row', 'tutor subjects1 subjects2 comment')
    tregs = model.TutorRegistration.all_in_session(session)
    rows = []
    for treg in tregs:
        subjects = model.TutorRegistrationSubject.all_of_treg(treg)
        rows.append(Row(
            model.Tutor.get(treg.uid),
            [model.Subject.get(x.sid) for x in subjects if x.preference == 1],
            [model.Subject.get(x.sid) for x in subjects if x.preference == 2],
            treg.comment
            ))
    def key(x):
        if x.subjects1:
            return min(map(operator.attrgetter('sid'), x.subjects1))
        else:
            return 1000000
    rows.sort(key=key)
    return rows

@check_hash('tutor')
def get_tutor_form_data(session, tutor):
    tutor = model.Tutor.get(int(tutor))
    try:
        treg = model.TutorRegistration.find(int(session), tutor)
        subjects = {(model.Subject.get(x.sid), x.preference)
                    for x in model.TutorRegistrationSubject.all_of_treg(treg)}
        group_size = treg.group_size
        comment = treg.comment
    except model.NotFound:
        subjects = set()
        group_size = 0
        comment = ''
    return TutorForm(tutor, subjects, group_size, comment)

@check_hash('tutor')
def set_tutor_form_data(session, tutor, subjects, group_size, comment):
    try:
        treg = model.TutorRegistration.find(int(session), int(tutor))
    except model.NotFound:
        treg = model.TutorRegistration.create(int(session), int(tutor), group_size, comment)
    else:
        treg.update(group_size, comment)
    model.TutorRegistrationSubject.set_for_treg(treg,
            ((model.Subject.get(int(x)), y) for (x,y) in subjects))
    return treg

@check_hash('student')
def get_student_form_data(session, student):
    session = int(session)
    student = model.Student.get(int(student))
    try:
        sreg = model.StudentRegistration.find(session, student)
        subject = model.Subject.get(sreg.suid)
        friends = sreg.friends
        comment = sreg.comment
    except model.NotFound:
        subject = None
        friends = 0
        comment = ''
    return StudentForm(student, subject, friends, comment)

@check_hash('student')
def set_student_form_data(session, student, subject, friends, comment):
    session = int(session)
    student = int(student)
    subject = model.Subject.get(int(subject))
    friends = int(friends)
    try:
        sreg = model.StudentRegistration.find(session, student)
    except model.NotFound:
        sreg = model.StudentRegistration.create(session, student,
                subject, friends, comment)
    else:
        sreg.update(subject, friends, comment)
    return sreg

def send_tutor_email(session, get_form_url, subject, content):
    tutors = model.Tutor.all_active()
    def pred(tutor):
        repl = {'nom_tuteur': tutor.name,
                'lien_formulaire_tuteur': get_form_url(tutor)
                }
        return (tutor.email,
                string.Template(subject).substitute(repl),
                string.Template(content).substitute(repl)
                )
    mails = model.Mail.create_many(map(pred, tutors))
    sender = emails.Sender()
    errors = []
    for mail in mails:
        try:
            sender.send(mail.recipient, mail.subject, mail.content)
        except smtplib.SMTPException as e:
            errors.append((mail, e))
        else:
            mail.set_sent()
    session.set_emailed_tutors()
    return errors


def read_contacts(fd):
    people = list(csv.reader(fd, delimiter=','))
    headers = people[0]
    people = list(map(lambda x:dict(zip(headers, x)), people[1:]))
    return people

def import_tutors(fd):
    raw = read_contacts(fd)
    nb_imported = 0
    nb_ignored = 0
    for row in raw:
        email = row['E-mail Address'].decode('latin1')
        name = '%s %s' % (row['First Name'], row['Last Name'])
        name = name.decode('latin1')
        try:
            model.Tutor.get(email)
        except model.NotFound:
            model.Tutor.create(email, name)
            nb_imported += 1
        else:
            nb_ignored += 1
            continue
    return (nb_imported, nb_ignored)
