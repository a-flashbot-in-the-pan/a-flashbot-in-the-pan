#!/usr/bin/env python3

import csv
import unittest

import pandas as pd

from tips import calculate_tip_dataframe

class TestTipCalc(unittest.TestCase):
    def setUp(self):
        self._sample_blocks = pd.read_json("resources/flashbots-blocks-test.json")
        self._single_frontrun_block = pd.read_json("resources/single-frontrunning-block.json")


    def test_tip_single_frontrun(self):
        """Test a few interesting cases."""

        tip = calculate_tip_dataframe(self._single_frontrun_block)
        self.assertEqual(tip, 1.0)


if __name__ == "__main__":
    unittest.main()
