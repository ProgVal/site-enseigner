# -*- coding: utf8 -*-
import os
import uuid
from flask import Flask, render_template, request, session, redirect, url_for
from flask import abort
from werkzeug.exceptions import HTTPException
from werkzeug.wrappers import Response

import model
from config import config

app = Flask('enseigner')
salt = config['password_salt']
assert len(salt) >= 20, 'Secret key is not long enough'
app.secret_key = salt

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

@app.route('/gestion_seances/')
@require_admin
def gestion_seances():
    return render_template('gestion_seances/index.html',
            sessions=model.Session.all())

@app.route('/gestion_seances/nouvelle/', methods=['GET', 'POST'])
@require_admin
def nouvelle_seance():
    if request.method == 'GET':
        return render_template('gestion_seances/nouvelle.html',
                               sessions=model.Session.all())
    else:
        s = controller.create_session(request.form['date'],
                filter(bool, request.form['subjects'].split('\n')))
        return redirect(url_for('gestion_seances'))


@app.route('/connexion/', methods=['GET', 'POST'])
def connexion():
    if request.method == 'GET':
        redirect_url = request.args.get('redirect_url', '')
        return render_template('connexion.html', redirect_url=redirect_url)
    elif request.method == 'POST':
        email = request.form.get('email', None)
        password = request.form.get('password', None)
        redirect_url = request.form.get('redirect_url', '')
        assert email and password, request.form
        tutor = model.Tutor.check_password(email, password)
        if not tutor:
            # TODO: Show an error message
            return render_template('connexion.html', redirect_url=redirect_url)
        else:
            session['tutor_id'] = tutor.uid
            return redirect('/' + redirect_url)
    else:
        raise AssertionError(request.method)
