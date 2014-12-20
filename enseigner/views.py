from flask import Flask, render_template
app = Flask('enseigner')

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
def gestion_seances():
    return render_template('gestion_seances.html')
