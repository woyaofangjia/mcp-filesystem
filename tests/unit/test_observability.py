"""可观测性模块单元测试"""
import pytest
from src.mcp_project.services.observability import (
    MetricsCollector, HealthChecker, AlertManager, AlertRule
)


class TestMetricsCollector:
    def test_record_and_stats(self):
        mc = MetricsCollector()
        mc.record_request("read_file", 50.0, success=True)
        mc.record_request("read_file", 100.0, success=True)
        mc.record_request("read_file", 200.0, success=False)

        stats = mc.get_tool_stats("read_file")
        assert stats["total_requests"] == 3
        assert stats["success"] == 2
        assert stats["errors"] == 1
        assert stats["error_rate"] == pytest.approx(33.33, abs=0.1)
        assert stats["avg_response_ms"] == pytest.approx(116.67, abs=0.1)

    def test_all_stats(self):
        mc = MetricsCollector()
        mc.record_request("tool_a", 10.0)
        mc.record_request("tool_b", 20.0)
        stats = mc.get_all_stats()
        assert stats["summary"]["total_requests"] == 2
        assert "tool_a" in stats["tools"]
        assert "tool_b" in stats["tools"]
        assert "system" in stats

    def test_reset(self):
        mc = MetricsCollector()
        mc.record_request("tool", 10.0)
        mc.reset()
        assert mc.get_all_stats()["summary"]["total_requests"] == 0


class TestHealthChecker:
    def test_all_healthy(self):
        hc = HealthChecker()
        hc.register_check("disk", lambda: True)
        hc.register_check("memory", lambda: True)
        result = hc.check_health()
        assert result["overall"] == "healthy"
        assert result["disk"] == "healthy"
        assert result["memory"] == "healthy"

    def test_unhealthy(self):
        hc = HealthChecker()
        hc.register_check("failing", lambda: False)
        result = hc.check_health()
        assert result["overall"] == "unhealthy"
        assert result["failing"] == "unhealthy"

    def test_check_exception(self):
        hc = HealthChecker()
        hc.register_check("broken", lambda: exec("raise Exception('boom')"))
        result = hc.check_health()
        assert result["overall"] == "unhealthy"
        assert "error" in result["broken"]


class TestAlertManager:
    def test_add_and_trigger(self):
        am = AlertManager(cooldown_seconds=0)
        rule = AlertRule(
            name="test",
            condition=lambda m: m.get("trigger", False) is True,
            message="triggered",
            severity="warning",
        )
        am.add_rule(rule)
        alerts = am.check({"trigger": True})
        assert len(alerts) == 1
        assert alerts[0]["rule"] == "test"

    def test_no_trigger(self):
        am = AlertManager()
        rule = AlertRule(
            name="test",
            condition=lambda m: m.get("trigger", False) is True,
            message="triggered",
        )
        am.add_rule(rule)
        alerts = am.check({"trigger": False})
        assert len(alerts) == 0

    def test_cooldown(self):
        am = AlertManager(cooldown_seconds=999)
        rule = AlertRule(
            name="test",
            condition=lambda m: True,
            message="always",
        )
        am.add_rule(rule)
        alerts1 = am.check({})
        alerts2 = am.check({})
        assert len(alerts1) == 1
        assert len(alerts2) == 0  # in cooldown

    def test_default_rules(self):
        am = AlertManager()
        rules = am.get_default_rules()
        assert len(rules) >= 4
        names = [r.name for r in rules]
        assert "high_error_rate" in names
        assert "high_disk_usage" in names
