from __future__ import annotations

import unittest
from pathlib import Path

from electrochem_core import merge_electrochem, read_electrochem
from plot_data import cd_plot_graphs, electrochem_plot_graphs
from spectrum_core import merge_exact_union, read_spectrum


FIXTURES = Path(__file__).resolve().parent / "fixtures"


class PlotDataTests(unittest.TestCase):
    def test_cd_defaults_create_cd_and_g_graphs(self) -> None:
        result = merge_exact_union(
            [read_spectrum(FIXTURES / "A.txt"), read_spectrum(FIXTURES / "B.txt")]
        )
        graphs = cd_plot_graphs(result, ("CD", "G"))
        self.assertEqual([graph.title for graph in graphs], ["CD", "G 因子"])
        self.assertEqual([series.name for series in graphs[0].series], ["CD1", "CD2"])
        self.assertEqual([series.name for series in graphs[1].series], ["G1", "G2"])
        self.assertTrue(graphs[0].reverse_x)

    def test_cd_preview_can_enable_optional_channels(self) -> None:
        result = merge_exact_union([read_spectrum(FIXTURES / "A.txt")])
        graphs = cd_plot_graphs(result, ("HT", "Abs"))
        self.assertEqual([graph.title for graph in graphs], ["HT", "Abs"])

    def test_electrochem_all_discovered_channels_become_graphs(self) -> None:
        result = merge_electrochem(
            [
                read_electrochem(FIXTURES / "OER_A.txt"),
                read_electrochem(FIXTURES / "OER_B.txt"),
            ]
        )
        graphs = electrochem_plot_graphs(result, result.channels)
        self.assertEqual([graph.title for graph in graphs], ["Current"])
        self.assertEqual(
            [series.name for series in graphs[0].series],
            ["Current1", "Current2"],
        )

    def test_preview_channel_filter_is_respected(self) -> None:
        result = merge_electrochem([read_electrochem(FIXTURES / "OER_A.txt")])
        self.assertEqual(electrochem_plot_graphs(result, ()), ())


if __name__ == "__main__":
    unittest.main(verbosity=2)
