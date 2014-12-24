#!/usr/bin/env python2
from enseigner import model

email = raw_input('email? ')
password = raw_input('password? ')
model.Tutor.create(email, password, None, True)
