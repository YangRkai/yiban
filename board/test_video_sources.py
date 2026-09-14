import unittest
from video_sources import choose_default
class DeviceChoice(unittest.TestCase):
    def test_prefers_obs_regardless_of_index(self):
        items=[('UGREEN 45647 [0]',0),('OBS Virtual Camera [2]',2)]
        self.assertEqual(choose_default(items),'OBS Virtual Camera [2]')
    def test_does_not_fall_back_to_hardware_without_obs(self):
        self.assertEqual(choose_default([('UGREEN 45647 [0]',0)]),'')
if __name__=='__main__':unittest.main()
