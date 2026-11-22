from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from spectrum_core import (
    DEFAULT_CHANNELS,
    DuplicateWavelengthError,
    SpectrumError,
    merge_exact_union,
    read_spectrum,
)


def write_raw(
    directory: Path,
    name: str,
    rows: list[tuple[float | str, ...]],
    *,
    blocks: int = 1,
) -> Path:
    path = directory / name
    lines = [
        "Sample Name\t测试样品",
        "Comment\tSignalWeave test",
    ]
    for _ in range(blocks):
        lines.append("XYDATA")
        lines.extend("\t".join(str(value) for value in row) for row in rows)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


class CoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_user_example_becomes_wide_exact_union(self) -> None:
        a = write_raw(
            self.root,
            "A.txt",
            [
                (900.0, 1, 10, 0.1),
                (899.5, 2, 20, 0.2),
                (899.0, 1.6, 30, 0.3),
            ],
        )
        b = write_raw(
            self.root,
            "B.txt",
            [
                (900.5, 5, 50, 0.5),
                (900.0, 5, 50, 0.5),
                (899.5, 2, 20, 0.2),
            ],
        )

        result = merge_exact_union([read_spectrum(a), read_spectrum(b)])

        self.assertEqual(
            result.header,
            (
                "Wavelength (nm)",
                "CD1", "HT1", "Abs1",
                "CD2", "HT2", "Abs2",
                "G1", "G2",
            ),
        )
        self.assertEqual(
            result.rows,
            (
                ("900.5", "", "", "", "5", "50", "0.5", "", ""),
                ("900.0", "1", "10", "0.1", "5", "50", "0.5", "", ""),
                ("899.5", "2", "20", "0.2", "2", "20", "0.2", "", ""),
                ("899.0", "1.6", "30", "0.3", "", "", "", "", ""),
            ),
        )
        self.assertEqual(result.missing_values, 6)
        lines = result.text.splitlines()
        self.assertEqual(lines[0].split("\t"), list(result.header))
        self.assertEqual(lines[1], "\t" * (result.column_count - 1))
        self.assertEqual(lines[2], "\t" * (result.column_count - 1))
        self.assertTrue(lines[3].startswith("900.5\t\t\t\t5\t50\t0.5\t"))
        self.assertTrue(lines[4].startswith("900.0\t1\t10\t0.1\t5\t50\t0.5\t"))
        self.assertEqual(
            result.formula_row[-2:],
            (
                'col("CD1")/(32982*col("Abs1"))',
                'col("CD2")/(32982*col("Abs2"))',
            ),
        )
        self.assertEqual(
            result.formula_text,
            '\t'.join(result.formula_row[-2:]),
        )
        self.assertEqual(result.row_count, 4)
        self.assertEqual(result.column_count, 9)

    def test_near_identical_wavelengths_share_one_row(self) -> None:
        a = write_raw(self.root, "A.txt", [(900.0, 1, 10, 0.1)])
        b = write_raw(self.root, "B.txt", [(900.0000005, 2, 20, 0.2)])

        result = merge_exact_union([read_spectrum(a), read_spectrum(b)])

        self.assertEqual(len(result.rows), 1)
        self.assertEqual(
            result.rows[0],
            ("900.0", "1", "10", "0.1", "2", "20", "0.2", "", ""),
        )

    def test_duplicate_wavelength_rejects_file(self) -> None:
        path = write_raw(
            self.root,
            "duplicate.txt",
            [
                (900.0, 1, 10, 0.1),
                (900.0000004, 2, 20, 0.2),
            ],
        )

        with self.assertRaises(DuplicateWavelengthError) as context:
            read_spectrum(path)
        self.assertIn("同一文件存在重复波长", str(context.exception))
        self.assertIn("900", str(context.exception))

    def test_channel_filter_keeps_only_selected_columns(self) -> None:
        a = write_raw(self.root, "A.txt", [(900.0, 1, 10, 0.1), (899.5, 2, 20, 0.2)])
        b = write_raw(self.root, "B.txt", [(900.0, 3, 30, 0.3)])

        result = merge_exact_union(
            [read_spectrum(a), read_spectrum(b)], channels=("CD",)
        )

        self.assertEqual(
            result.header, ("Wavelength (nm)", "CD1", "CD2")
        )
        self.assertEqual(
            result.rows,
            (
                ("900.0", "1", "3"),
                ("899.5", "2", ""),
            ),
        )
        self.assertEqual(result.formula_row, ("", "", ""))

    def test_missing_channels_are_blank(self) -> None:
        path = write_raw(
            self.root,
            "cd-only.txt",
            [
                (900.0, 1),
                (899.5, 2),
            ],
        )

        spectrum = read_spectrum(path)
        result = merge_exact_union([spectrum])

        self.assertEqual(spectrum.channel_names, ("CD",))
        self.assertEqual(result.rows[0], ("900.0", "1", "", "", ""))
        self.assertEqual(result.missing_values, 4)

    def test_preserves_original_number_text(self) -> None:
        path = write_raw(
            self.root,
            "precision.txt",
            [
                ("900.00", "1.2300", "864.196", "0.411691"),
                ("899.50", "2.0000", "864.945", "0.423066"),
            ],
        )

        spectrum = read_spectrum(path)
        result = merge_exact_union([spectrum], channels=DEFAULT_CHANNELS)

        self.assertEqual(
            result.rows[0],
            ("900.00", "1.2300", "864.196", "0.411691", ""),
        )
        self.assertEqual(
            result.rows[1],
            ("899.50", "2.0000", "864.945", "0.423066", ""),
        )

    def test_multiple_xydata_blocks_fail_clearly(self) -> None:
        path = write_raw(
            self.root,
            "multi.txt",
            [
                (900.0, 1, 10, 0.1),
            ],
            blocks=2,
        )

        with self.assertRaises(SpectrumError) as context:
            read_spectrum(path)
        self.assertIn("多个 XYDATA", str(context.exception))

    def test_unsupported_extension_fails_clearly(self) -> None:
        path = self.root / "data.csv"
        path.write_text("XYDATA\n900.0\t1\t2\t3\n", encoding="utf-8")

        with self.assertRaises(SpectrumError) as context:
            read_spectrum(path)
        self.assertIn("原始 .txt", str(context.exception))


if __name__ == "__main__":
    unittest.main(verbosity=2)
