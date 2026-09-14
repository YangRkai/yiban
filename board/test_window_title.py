import unittest
from window_output import same_board_window_title

class FoxTitle(unittest.TestCase):
    def test_move_and_status_updates_keep_calibration(self):
        title='野狐围棋 > [高级房1] > 241175号房间 对弈中 [第1手] - 友谊赛 - 数子规则'
        for move in (2,3,40,200):
            self.assertTrue(same_board_window_title(title,title.replace('[第1手]',f'[第{move}手]')))
        self.assertTrue(same_board_window_title(title,title.replace('对弈中','对局结束（黑中盘胜）')))
    def test_room_or_page_change_is_rejected(self):
        title='241175号房间 对弈中 [第1手]'
        self.assertFalse(same_board_window_title(title,'241176号房间 对弈中 [第1手]'))
        self.assertFalse(same_board_window_title(title,'野狐围棋 大厅'))
        self.assertFalse(same_board_window_title('其他窗口','另一个窗口'))
    def test_alternate_room_format(self):
        self.assertTrue(same_board_window_title('241175房间 [第1手]','241175号房间 [第2手]'))
