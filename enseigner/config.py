import os
import json

with open(os.environ['ENSEIGNER_CONFIG']) as fd:
    config = json.load(fd)
