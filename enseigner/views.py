# -*- coding: utf8 -*-
import os
import uuid
import collections
from flask import Flask, render_template, request, session, redirect, url_for
from flask import abort, Response
from werkzeug.exceptions import HTTPException
from werkzeug.wrappers import Response

import model
import emails
import controller
from config import config

app = Flask('enseigner')
salt = config['password_salt']
assert len(salt) >= 20, 'Secret key is not long enough'
app.secret_key = salt

TUTORS_EMAIL_SUBJECT = u'ENSeigner — Participation à la séance du %(date)s'
TUTORS_EMAIL_CONTENT = u'''Bonjour $nom_tuteur,

Voici, comme chaque semaine, le lien vers le formulaire pour participer à
la séance de samedi prochain en tant que tuteur-trice :
$lien_formulaire_tuteur

Cordialement,
Les reponsables du soutien'''

STUDENTS_EMAIL_SUBJECT = u'ENSeigner — Inscription à la séance du %(date)s'
STUDENTS_EMAIL_CONTENT = u'''Bonjour $nom_eleve,

Voici, comme chaque semaine, le lien vers le formulaire pour t’inscrire à
la séance de samedi prochain en temps qu’élève :
$lien_formulaire_eleve

Cordialement,
Les reponsables du soutien'''

class AdminOnly(HTTPException):
    def get_response(self, environ=None):
        html = render_template('erreur.html', admin_only=True,
                error_message=u'Accès réservé aux responsables du soutien.')
        return Response(html, mimetype='text/html')

def require_admin(f):
    def newf(**kwargs):
        try:
            id = session.get('tutor_id', None)
            if not id:
                raise model.NotFound()
            tutor = model.Tutor.get(id)
        except model.NotFound:
            url = url_for(f.__name__, **kwargs).lstrip('/')
            return redirect(url_for('connexion', redirect_url=url))
        else:
            if tutor.is_admin:
                return f(**kwargs)
            else:
                raise AdminOnly()
    newf.__name__ = f.__name__
    return newf


# From http://flask.pocoo.org/snippets/3/
@app.before_request
def csrf_protect():
    if request.method == "POST":
        token = session.pop('_csrf_token', None)
        if not token or token != request.form.get('_csrf_token'):
            abort(403)
def generate_csrf_token():
    if '_csrf_token' not in session:
        session['_csrf_token'] = str(uuid.uuid4())
    return session['_csrf_token']
app.jinja_env.globals['csrf_token'] = generate_csrf_token        

@app.route('/')
def accueil():
    return render_template('accueil.html')

@app.route('/inscription/')
def inscription():
    return render_template('inscription.html')

@app.route('/prochaines_seances/')
def prochaines_seances():
    return render_template('prochaines_seances.html')

@app.route('/gestion_soutien/')
@require_admin
def gestion_soutien():
    return render_template('gestion_soutien/index.html',
            sessions=model.Session.all())

@app.route('/gestion_soutien/liste_tuteurs_seance/')
@require_admin
def liste_tuteurs_seance():
    session = model.Session.get(int(request.args['session']))
    rows = controller.get_tutor_registration_list_rows(session)

    if request.args.get('download', 'false') == 'true':
        def pred(row):
            return '%s;%s;%s;%s;%s' % (
                    row.tutor.name,
                    row.tutor.email,
                    ', '.join(x.name for x in row.subjects1),
                    ', '.join(x.name for x in row.subjects2),
                    row.comment)
        response = Response('\n'.join(map(pred, rows)),
                mimetype='text/csv')
        response.headers["Content-Disposition"] = "attachment; filename=Tuteurs_seance.csv"
        return response
    else:
        return render_template('gestion_soutien/liste_tuteurs_seance.html',
                session=session,
                rows=rows)

@app.route('/gestion_soutien/nouvelle/', methods=['GET', 'POST'])
@require_admin
def nouvelle_seance():
    if request.method == 'POST':
        invalid = set(x for x in ('date',) if not request.form.get(x, ''))
        if 'date' not in invalid:
            try:
                controller.parse_human_date(request.form['date'])
            except ValueError:
                invalid.add('date')
    else:
        invalid = []
    if request.method == 'GET' or invalid:
        return render_template('gestion_soutien/nouvelle.html',
                               sessions=model.Session.all(),
                               invalid=invalid,
                               form=request.form)
    else:
        s = controller.create_session(request.form['date'],
                filter(bool, request.form['subjects'].split('\n')))
        return redirect(url_for('gestion_soutien'))

def mail_get_invalid():
    if request.method == 'POST':
        invalid = set(x for x in ('subject', 'content')
                      if not request.form.get(x, ''))
        return invalid
    else:
        return []
@app.route('/gestion_soutien/envoi_mail_seance/tuteurs/', methods=['GET', 'POST'])
def envoi_mail_tuteurs():
    session = model.Session.get(int(request.args['session']))
    invalid = mail_get_invalid()
    if request.method == 'POST' and not invalid:
        subject = request.form['subject']
        content = request.form['content']
        def get_form_url(tutor):
            key = controller.hash_subscription_params(session.sid, 'tutor', tutor.uid)
            return url_for('formulaire_tuteur', _external=True,
                    session=session.sid,
                    tuteur=tutor.uid,
                    key=key
                    )
        errors = controller.send_tutor_email(session, get_form_url, subject, content)
        if not errors:
            return redirect(url_for('gestion_soutien'))
    elif request.method == 'POST':
        errors = ['Un ou des champs est/sont invalide-s']
    else:
        errors = []

    subj_repl = {'date': session.date.strftime('%d/%m/%Y')}
    subject = request.form.get('subject', '') or \
            TUTORS_EMAIL_SUBJECT % subj_repl
    content = request.form.get('content', '') or TUTORS_EMAIL_CONTENT
    return render_template('gestion_soutien/envoi_mail.html',
                           recipient='Tuteurs et tutrices',
                           sender=config['email']['from'],
                           subject=subject,
                           content=content,
                           errors=errors,
                           invalid=invalid)
        
@app.route('/gestion_soutien/envoi_mail_seance/eleves/', methods=['GET', 'POST'])
def envoi_mail_eleves():
    session = model.Session.get(int(request.args['session']))
    invalid = mail_get_invalid()
    if request.method == 'GET' or invalid:
        subj_repl = {'date': session.date.strftime('%d/%m/%Y')}
        subject = request.form.get('subject', '') or \
                STUDENTS_EMAIL_SUBJECT % subj_repl
        content = request.form.get('content', '') or STUDENTS_EMAIL_CONTENT
        return render_template('gestion_soutien/envoi_mail.html',
                               recipient=u'Élèves',
                               sender=config['email']['from'],
                               subject=subject,
                               content=content,
                               invalid=invalid)

@app.route('/connexion/', methods=['GET', 'POST'])
def connexion():
    if request.method == 'GET':
        redirect_url = request.args.get('redirect_url', '')
        return render_template('connexion.html', redirect_url=redirect_url,
                just_redirected=True)
    elif request.method == 'POST':
        email = request.form.get('email', None)
        password = request.form.get('password', None)
        redirect_url = request.form.get('redirect_url', '')
        assert email and password, request.form
        tutor = model.Tutor.check_password(email, password)
        if not tutor:
            return render_template('connexion.html',
                    redirect_url=redirect_url,
                    wrong_login=True)
        else:
            session['tutor_id'] = tutor.uid
            return redirect('/' + redirect_url)
    else:
        raise AssertionError(request.method)

@app.route('/formulaires/tuteur/', methods=['GET', 'POST'])
def formulaire_tuteur():
    session = model.Session.get(int(request.args['session']))
    tutor = model.Tutor.get(int(request.args['tuteur']))
    key = request.args['key']
    if request.method == 'POST':
        subjects = [(x, 1) for x in request.form.getlist('subjects1')]
        subjects.extend([(x, 2) for x in request.form.getlist('subjects2')])
        controller.set_tutor_form_data(session.sid, tutor.uid, key,
                subjects,
                request.form['group_size'], request.form['comment'])
        success = True 
    else:
        success = False
    form = controller.get_tutor_form_data(session.sid, tutor.uid, key)
    session_subjects = model.SessionSubject.all_subjects_for_session(session)
    return render_template('formulaires/tuteur.html',
            form=form,
            success=success,
            session_subjects=sorted(session_subjects, key=lambda x:x.name))
