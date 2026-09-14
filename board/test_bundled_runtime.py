import json
import tempfile
import unittest
from pathlib import Path
from bundled_runtime import prepare_bundled_cpu
class BundledRuntimeTests(unittest.TestCase):
 def test_clean_install_and_relocation(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp); folder=root/'engine-cpu';folder.mkdir()
   self.assertFalse(prepare_bundled_cpu(root))
   for name in ('katago.exe','model.txt.gz','gtp.cfg'):(folder/name).touch()
   self.assertTrue(prepare_bundled_cpu(root))
   config=root/'board/runtime.cpu.json'
   self.assertEqual(json.loads(config.read_text())['executable'],str(folder/'katago.exe'))
   config.write_text(json.dumps({'bundled':True,'executable':'old/path'}))
   prepare_bundled_cpu(root)
   self.assertEqual(json.loads(config.read_text())['executable'],str(folder/'katago.exe'))
   config.write_text(json.dumps({'executable':'custom.exe'}))
   prepare_bundled_cpu(root)
   self.assertEqual(json.loads(config.read_text())['executable'],'custom.exe')
