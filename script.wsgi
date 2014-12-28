import os, sys
if 'ENSEIGNER_CONFIG' not in os.environ:
    os.environ['ENSEIGNER_CONFIG'] = os.path.join(
        os.path.dirname(__file__),
        'config.json')
sys.path.append(os.path.dirname(__file__))
from enseigner import app as application
