#!/usr/bin/env python2
# -*- coding: utf8 -*-
import smtplib
import enseigner.model as model
import enseigner.emails as emails

mails = model.Mail.all_unsent()

yesno = raw_input(u'Envoyer %d mails ? ' % len(mails))

if yesno != 'yes':
    exit(0)

sender = emails.Sender()
errors = []
for mail in mails:
    try:
        sender.send(mail.recipient, mail.subject, mail.content)
    except smtplib.SMTPException as e:
        errors.append((mail, e))
    else:
        mail.set_sent()

print(repr(errors))
with open('/tmp/enseigner_errors.txt', 'a') as fd:
    for error in errors:
        fd.write('\n\n')
        fd.write(repr(error))
