#!/usr/bin/env python2
import os
import unittest

import enseigner.emails

def main(): # pragma: no cover
    enseigner.emails.Sender = enseigner.emails.MockServer
    testsuite = unittest.TestLoader().discover('tests/')
    results = unittest.TextTestRunner(verbosity=1).run(testsuite)
    if results.errors or results.failures:
        exit(1)
    else:
        exit(0)

if __name__ == '__main__':
    main()
