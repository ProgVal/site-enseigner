import collections
from email.mime.text import MIMEText

from config import config

class Sender(object):
    def __init__(self):
        self.server = smtplib.SMTP(config['email']['server'])
        self.server.starttls()
        self.server.login(config['email']['username'],
                config['email']['password'])

    def __die__(self):
        self.server.quit()

    def send(self, recipient, subject, content):
        msg = MIMEText(content)
        msg['Subject'] = subject
        msg['From'] = config['email']['from']
        msg['To'] = recipient
        msg['Cci'] = config['email']['cci']
        self.server.sendmail(config['email']['from'], recipient,
                msg.as_string())

class MockSender(object):
    queue = []

    def send(self, recipient, subject, content):
        self.queue.append((recipient, subject, content))
