__author__ = 'dressman'

import unittest
import pyostat.util
import mock
import os.path

from tests import __file__ as test_directory

def data_dir():
    return os.path.join(os.path.dirname(test_directory), 'data')

class IostatTestCase(unittest.TestCase):

    def setUp(self):
        self.proc_uptime = os.path.join(data_dir(), 'proc_uptime.txt')
        self.proc_diskstats = os.path.join(data_dir(), 'proc_diskstats.txt')


    def test_read_uptime(self):
        uptime = pyostat.util.read_uptime(self.proc_uptime)

        self.assertEqual(len(uptime), 2)
        self.assertIs(type(uptime[0]), float)
        self.assertIs(type(uptime[1]), float)


    def test_quotient(self):

        self.assertEqual(0.0, pyostat.util._quotient(1.3, 0.0))
        self.assertEqual(2.0, pyostat.util._quotient(4.0, 2.0))


if __name__ == '__main__':
    unittest.main()
