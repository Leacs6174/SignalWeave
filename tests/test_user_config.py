from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from user_config import (
    CD_MERGE_DEFAULT,
    CD_PREVIEW_DEFAULT,
    UserConfig,
    DEFAULT_MARKER_SIZE,
    DEFAULT_SERIES_COLORS,
    load_user_config,
    save_user_config,
    selected_channels,
    with_channels,
)


class UserConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_defaults_match_product_requirements(self) -> None:
        config = UserConfig()
        self.assertEqual(config.cd_merge_channels, CD_MERGE_DEFAULT)
        self.assertEqual(config.cd_preview_channels, CD_PREVIEW_DEFAULT)
        self.assertIsNone(config.electrochem_merge_channels)
        self.assertIsNone(config.electrochem_preview_channels)
        self.assertEqual(config.theme_mode, "light")
        self.assertEqual(config.render_mode, "line")
        self.assertEqual(config.marker_size, DEFAULT_MARKER_SIZE)
        self.assertEqual(config.series_colors, DEFAULT_SERIES_COLORS)
        self.assertEqual(
            selected_channels(("Current", "Potential"), None, default_all=True),
            ("Current", "Potential"),
        )

    def test_round_trip_keeps_merge_and_preview_channels(self) -> None:
        path = self.root / "DataMerger-config.json"
        expected = UserConfig(
            cd_merge_channels=("CD", "Abs"),
            cd_preview_channels=("CD", "HT", "G"),
            electrochem_merge_channels=("Current",),
            electrochem_preview_channels=("Current", "Potential"),
            theme_mode="dark",
            font_family="Segoe UI",
            font_size=13,
            render_mode="scatter",
            marker_size=2.4,
            series_colors=("#112233", "#445566"),
        )
        save_user_config(path, expected)
        self.assertEqual(load_user_config(path), expected)

    def test_invalid_config_falls_back_to_defaults(self) -> None:
        path = self.root / "bad.json"
        path.write_text("{bad", encoding="utf-8")
        self.assertEqual(load_user_config(path), UserConfig())

    def test_channel_replacement_deduplicates(self) -> None:
        config = with_channels(UserConfig(), "cd_preview_channels", ["G", "CD", "G"])
        self.assertEqual(config.cd_preview_channels, ("G", "CD"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
