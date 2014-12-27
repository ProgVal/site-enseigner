#!/usr/bin/env python2
from enseigner import model

name = raw_input('name? ')
email = raw_input('email? ')
password = raw_input('password? ')
model.Tutor.create(email, name, password, None, True)
