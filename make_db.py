#!/usr/bin/env python2
# -*- coding: utf8 -*-
import csv
import sys
import enseigner.model as model

SUBJECTS = u'''
Mathématiques
Physique-Chimie : Physique
Physique-Chimie : Chimie
Sciences de la Vie et de la Terre : Biologie
Sciences de la Vie et de la Terre : Géologie
Français
Philosophie
Allemand
Anglais
Espagnol
Histoire
Géographie
Informatique et Sciences du Numérique
Sciences de l’Ingénieur
Sciences Économiques et Sociales
'''

conn = model.get_conn()
with conn:
    for table in model.tables:
        conn.execute(table._create_table)

for subject in filter(bool, SUBJECTS.split('\n')):
    model.Subject.create(subject, False)
