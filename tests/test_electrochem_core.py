from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from electrochem_core import (
    ElectrochemError,
    merge_electrochem,
    read_electrochem,
)


FIXTURES = Path(__file__).resolve().parent / "fixtures"


def write_chi(path: Path, header: str, rows: list[tuple[str, ...]]) -> Path:
    path.write_text(
        "\n".join(
            [
                "Nov. 19, 2026 10:00:00",
                "Electrochemical test",
                "",
                header,
                *[", ".join(row) for row in rows],
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return path


class ElectrochemCoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_detects_potential_as_x_axis(self) -> None:
        signal = read_electrochem(FIXTURES / "OER_A.txt")
        self.assertEqual(signal.axis.label, "Potential (V)")
        self.assertEqual(signal.channel_names, ("Current",))
        self.assertEqual(signal.x_values, (0.3, 0.301, 0.302))

    def test_detects_time_as_x_axis(self) -> None:
        signal = read_electrochem(FIXTURES / "GCD_A.txt")
        self.assertEqual(signal.axis.label, "Time (sec)")
        self.assertEqual(signal.channel_names, ("Potential",))
        self.assertEqual(signal.points, 3)

    def test_merge_is_exact_union_with_blank_missing_cells(self) -> None:
        result = merge_electrochem(
            [
                read_electrochem(FIXTURES / "OER_A.txt"),
                read_electrochem(FIXTURES / "OER_B.txt"),
            ]
        )
        self.assertEqual(result.header, ("Potential (V)", "Current1", "Current2"))
        self.assertEqual(
            result.rows,
            (
                ("0.300", "-3.368e-7", "-1.000e-7"),
                ("0.301", "-2.826e-7", "-9.000e-8"),
                ("0.302", "-2.486e-7", ""),
                ("0.303", "", "-7.000e-8"),
            ),
        )
        self.assertEqual(result.missing_values, 2)
        lines = result.text.splitlines()
        self.assertEqual(lines[0].split("\t"), list(result.header))
        self.assertEqual(lines[1], "\t\t")
        self.assertEqual(lines[2], "\t\t")
        self.assertEqual(lines[3].split("\t"), list(result.rows[0]))

    def test_same_time_axis_merges_side_by_side(self) -> None:
        result = merge_electrochem(
            [
                read_electrochem(FIXTURES / "GCD_A.txt"),
                read_electrochem(FIXTURES / "GCD_B.txt"),
            ]
        )
        self.assertEqual(
            result.header, ("Time (sec)", "Potential1", "Potential2")
        )
        self.assertEqual(result.row_count, 5)
        self.assertEqual(result.rows[0][0], "0.000e+0")
        self.assertEqual(result.rows[1][0], "0.005e+0")
        self.assertEqual(
            result.rows[2], ("1.000e-2", "-1.431e-1", "-1.400e-1")
        )

    def test_repeated_cv_potential_preserves_both_scan_directions(self) -> None:
        signal = read_electrochem(FIXTURES / "CV_LOOP.txt")
        result = merge_electrochem([signal])
        self.assertEqual(result.row_count, 5)
        self.assertEqual(
            result.rows,
            (
                ("-0.1", "1.0e-6"),
                ("-0.1", "5.0e-6"),
                ("0.0", "2.0e-6"),
                ("0.0", "4.0e-6"),
                ("0.1", "3.0e-6"),
            ),
        )

    def test_mixed_axes_are_rejected(self) -> None:
        with self.assertRaises(ElectrochemError) as context:
            merge_electrochem(
                [
                    read_electrochem(FIXTURES / "OER_A.txt"),
                    read_electrochem(FIXTURES / "GCD_A.txt"),
                ]
            )
        self.assertIn("横坐标不一致", str(context.exception))

    def test_multi_column_header_places_all_series_before_next_file(self) -> None:
        first = write_chi(
            self.root / "eis_a.txt",
            "Freq (Hz), Z' (ohm), Phase (deg)",
            [("1.0", "10.0", "-5.0"), ("0.1", "20.0", "-10.0")],
        )
        second = write_chi(
            self.root / "eis_b.txt",
            "Freq (Hz), Z' (ohm), Phase (deg)",
            [("2.0", "11.0", "-4.0"), ("1.0", "12.0", "-6.0")],
        )
        result = merge_electrochem(
            [read_electrochem(first), read_electrochem(second)]
        )
        self.assertEqual(
            result.header,
            ("Freq (Hz)", "Z'1", "Phase1", "Z'2", "Phase2"),
        )
        self.assertEqual(
            result.rows,
            (
                ("0.1", "20.0", "-10.0", "", ""),
                ("1.0", "10.0", "-5.0", "12.0", "-6.0"),
                ("2.0", "", "", "11.0", "-4.0"),
            ),
        )

    def test_merge_channel_filter_controls_export_columns(self) -> None:
        path = write_chi(
            self.root / "eis.txt",
            "Freq (Hz), Z' (ohm), Phase (deg)",
            [("1.0", "10.0", "-5.0"), ("0.1", "20.0", "-10.0")],
        )
        result = merge_electrochem(
            [read_electrochem(path)], channels=("Phase",)
        )
        self.assertEqual(result.header, ("Freq (Hz)", "Phase1"))
        self.assertEqual(result.channels, ("Phase",))
        self.assertEqual(
            [(item.channel, item.header) for item in result.series],
            [("Phase", "Phase1")],
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
