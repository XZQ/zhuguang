"""Contract tests for the read-only incident command-center HTML."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from dianxun.command_center import _SCENARIO_META, _temperature_svg, build_command_center


class CommandCenterTests(unittest.TestCase):
    """The HTML must mirror the M4 gate and the two safety red lines."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory(prefix="dianxun-cc-test-")
        cls.output_path = Path(cls._tmp.name) / "command-center.html"
        build_command_center(output_path=cls.output_path)
        cls.html = cls.output_path.read_text(encoding="utf-8")

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def test_all_six_scenarios_render_as_tabs_and_panels(self) -> None:
        self.assertEqual(6, self.html.count('<button class="tab'))
        for index in range(6):
            self.assertIn(f'id="panel-{index}"', self.html)
        for scenario_id, meta in _SCENARIO_META.items():
            self.assertIn(meta["title"], self.html, scenario_id)
            self.assertIn(meta["branch"], self.html, scenario_id)

    def test_redline_copy_is_present(self) -> None:
        self.assertIn("执行者不能自证成功", self.html)
        self.assertIn("设备恢复 ≠ 商品安全", self.html)
        self.assertIn("工单完成 ≠ 事件关闭", self.html)
        for meta in _SCENARIO_META.values():
            self.assertIn(meta["redline"], self.html)

    def test_auditor_verdict_block_per_scenario(self) -> None:
        self.assertEqual(6, self.html.count("<h3>Auditor 判决</h3>"))

    def test_temperature_svg_per_scenario(self) -> None:
        self.assertEqual(6, self.html.count("<svg"))
        svg = _temperature_svg(
            [
                {"observed_at": "2026-09-01T09:00:00+08:00", "temp_c": 4.0, "quality": "good"},
                {"observed_at": "2026-09-01T09:01:00+08:00", "temp_c": 4.2, "quality": "good"},
                {
                    "observed_at": "2026-09-01T09:02:00+08:00",
                    "temp_c": 12.0,
                    "quality": "suspect",
                },
                {"observed_at": "2026-09-01T09:03:00+08:00", "temp_c": 4.1, "quality": "good"},
                {"observed_at": "2026-09-01T09:04:00+08:00", "temp_c": 4.0, "quality": "good"},
            ]
        )
        self.assertEqual(2, svg.count("<polyline"))
        self.assertIn('fill="#f59e0b"', svg)

    def test_kpis_match_the_m4_gate(self) -> None:
        for fragment in (
            '<div class="kpi-v">6/6</div><div class="kpi-k">场景通过</div>',
            '<div class="kpi-v">0 / 0</div><div class="kpi-k">错误关闭 / 错误放行</div>',
            '<div class="kpi-v">0 / 0</div><div class="kpi-k">未授权 / 未审批写</div>',
            '<div class="kpi-v">45/45</div><div class="kpi-k">Evidence 完整率</div>',
            '<div class="kpi-v">26/26</div><div class="kpi-k">Trace 覆盖</div>',
        ):
            self.assertIn(fragment, self.html)

    def test_scope_disclaimer_is_present(self) -> None:
        self.assertIn("仅证明仓库内确定性行为", self.html)

    def test_render_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory(prefix="dianxun-cc-test-") as temporary:
            rerun_path = Path(temporary) / "rerun.html"
            build_command_center(output_path=rerun_path)
            self.assertEqual(self.html, rerun_path.read_text(encoding="utf-8"))


class CommandCenterCliTests(unittest.TestCase):
    def test_cli_writes_html_and_returns_zero(self) -> None:
        from dianxun.cli import main

        with tempfile.TemporaryDirectory(prefix="dianxun-cc-cli-") as temporary:
            target = Path(temporary) / "cc.html"
            exit_code = main(["command-center", "--output", str(target)])
            self.assertEqual(0, exit_code)
            self.assertTrue(target.exists())
            self.assertIn("事故指挥台", target.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
