import unittest
from unittest.mock import patch
from types import SimpleNamespace
from app import BoardApp

class BackendSettings(unittest.TestCase):
    def test_worker_initialization_uses_plain_backend_value(self):
        class TkValue:
            def get(self):raise AssertionError('worker accessed Tk variable')
        app=SimpleNamespace(active_compute='CPU',compute=TkValue(),closed=False)
        with patch('app.Engine') as engine:
            engine.return_value.snapshot.return_value={'stones':{}}
            self.assertEqual(BoardApp.initialize(app),{'stones':{}})
            engine.assert_called_once_with(backend='cpu')
