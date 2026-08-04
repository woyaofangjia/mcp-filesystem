"""可观测性服务

提供健康检查、性能指标收集和告警功能。
"""

import time
import psutil
import os
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock, RLock
from typing import Any, Callable, Dict, List, Optional, Deque

from .logger import get_logger


@dataclass
class MetricPoint:
    """单个指标数据点"""
    timestamp: float
    value: float
    labels: Dict[str, str] = field(default_factory=dict)


class MetricsCollector:
    """性能指标收集器

    收集和查询：
    - 响应时间（每个工具）
    - 吞吐量（每秒请求数）
    - 错误率
    - 缓存命中率
    - 系统资源使用
    """

    def __init__(self, history_size: int = 1000):
        self._history_size = history_size
        self._lock = RLock()  # 可重入锁，避免get_all_stats调用get_tool_stats时死锁

        # 指标存储
        self._response_times: Dict[str, Deque[MetricPoint]] = defaultdict(
            lambda: deque(maxlen=history_size)
        )
        self._error_counts: Dict[str, int] = defaultdict(int)
        self._success_counts: Dict[str, int] = defaultdict(int)
        self._request_timestamps: Deque[float] = deque(maxlen=history_size)

        # 系统指标
        self._process = psutil.Process(os.getpid())

        self._logger = get_logger("metrics")

    def record_request(
        self,
        tool_name: str,
        duration_ms: float,
        success: bool = True,
    ) -> None:
        """记录一次请求"""
        with self._lock:
            self._response_times[tool_name].append(
                MetricPoint(timestamp=time.time(), value=duration_ms)
            )
            if success:
                self._success_counts[tool_name] += 1
            else:
                self._error_counts[tool_name] += 1
            self._request_timestamps.append(time.time())

    def get_tool_stats(self, tool_name: str) -> Dict[str, Any]:
        """获取单个工具的统计"""
        with self._lock:
            times = list(self._response_times.get(tool_name, []))
            if not times:
                return {"tool": tool_name, "requests": 0}

            values = [p.value for p in times]
            success = self._success_counts.get(tool_name, 0)
            errors = self._error_counts.get(tool_name, 0)
            total = success + errors

            return {
                "tool": tool_name,
                "total_requests": total,
                "success": success,
                "errors": errors,
                "error_rate": round(errors / total * 100, 2) if total > 0 else 0,
                "avg_response_ms": round(sum(values) / len(values), 2),
                "min_response_ms": round(min(values), 2),
                "max_response_ms": round(max(values), 2),
                "p50_response_ms": round(sorted(values)[len(values) // 2], 2),
                "p99_response_ms": round(sorted(values)[int(len(values) * 0.99)], 2),
            }

    def get_all_stats(self) -> Dict[str, Any]:
        """获取所有工具的统计"""
        with self._lock:
            tool_names = set(self._response_times.keys()) | set(self._error_counts.keys()) | set(self._success_counts.keys())
            tools = {name: self.get_tool_stats(name) for name in tool_names}

            # 吞吐量（最近60秒）
            now = time.time()
            recent = [t for t in self._request_timestamps if now - t < 60]
            throughput = len(recent) / 60 if recent else 0

            total_success = sum(self._success_counts.values())
            total_errors = sum(self._error_counts.values())
            total = total_success + total_errors

            return {
                "summary": {
                    "total_requests": total,
                    "total_success": total_success,
                    "total_errors": total_errors,
                    "overall_error_rate": round(total_errors / total * 100, 2) if total > 0 else 0,
                    "throughput_per_min": round(throughput * 60, 2),
                },
                "tools": tools,
                "system": self._get_system_stats(),
            }

    def _get_system_stats(self) -> Dict[str, Any]:
        """获取系统资源使用情况"""
        try:
            mem = self._process.memory_info()
            cpu_percent = self._process.cpu_percent(interval=None)
            disk = psutil.disk_usage(os.getcwd())

            return {
                "cpu_percent": round(cpu_percent, 2),
                "memory_rss_mb": round(mem.rss / 1024 / 1024, 2),
                "memory_vms_mb": round(mem.vms / 1024 / 1024, 2),
                "disk_total_gb": round(disk.total / 1024 / 1024 / 1024, 2),
                "disk_used_gb": round(disk.used / 1024 / 1024 / 1024, 2),
                "disk_free_gb": round(disk.free / 1024 / 1024 / 1024, 2),
                "disk_percent": round(disk.percent, 2),
                "threads": self._process.num_threads(),
                "pid": self._process.pid,
            }
        except Exception as e:
            return {"error": str(e)}

    def reset(self) -> None:
        """重置所有指标"""
        with self._lock:
            self._response_times.clear()
            self._error_counts.clear()
            self._success_counts.clear()
            self._request_timestamps.clear()


class HealthChecker:
    """健康检查器

    检查服务各组件的健康状态。
    """

    def __init__(self):
        self._checks: Dict[str, Callable[[], bool]] = {}
        self._logger = get_logger("health")

    def register_check(self, name: str, check_fn: Callable[[], bool]) -> None:
        """注册健康检查项"""
        self._checks[name] = check_fn

    def check_health(self) -> Dict[str, Any]:
        """执行所有健康检查"""
        results: Dict[str, Any] = {}
        all_healthy = True

        for name, check_fn in self._checks.items():
            try:
                healthy = check_fn()
                results[name] = "healthy" if healthy else "unhealthy"
                if not healthy:
                    all_healthy = False
            except Exception as e:
                results[name] = f"error: {e}"
                all_healthy = False

        results["overall"] = "healthy" if all_healthy else "unhealthy"
        results["timestamp"] = datetime.now(timezone.utc).isoformat()
        return results


class AlertRule:
    """告警规则"""

    def __init__(
        self,
        name: str,
        condition: Callable[[Dict[str, Any]], bool],
        message: str,
        severity: str = "warning",
    ):
        self.name = name
        self.condition = condition
        self.message = message
        self.severity = severity  # info / warning / critical
        self.last_triggered: Optional[float] = None
        self.trigger_count = 0


class AlertManager:
    """告警管理器

    基于规则检测异常并触发告警。
    """

    def __init__(self, cooldown_seconds: int = 300):
        self._rules: List[AlertRule] = []
        self._cooldown = cooldown_seconds
        self._history: Deque[Dict[str, Any]] = deque(maxlen=100)
        self._logger = get_logger("alerts")

    def add_rule(self, rule: AlertRule) -> None:
        """添加告警规则"""
        self._rules.append(rule)
        self._logger.info(f"告警规则已添加: {rule.name}")

    def check(self, metrics: Dict[str, Any]) -> List[Dict[str, Any]]:
        """检查所有规则，返回触发的告警"""
        triggered: List[Dict[str, Any]] = []
        now = time.time()

        for rule in self._rules:
            # 冷却期检查
            if rule.last_triggered and now - rule.last_triggered < self._cooldown:
                continue

            try:
                if rule.condition(metrics):
                    alert = {
                        "rule": rule.name,
                        "message": rule.message,
                        "severity": rule.severity,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                    triggered.append(alert)
                    rule.last_triggered = now
                    rule.trigger_count += 1
                    self._history.append(alert)

                    if rule.severity == "critical":
                        self._logger.error(f"严重告警: {rule.message}")
                    elif rule.severity == "warning":
                        self._logger.warning(f"告警: {rule.message}")
                    else:
                        self._logger.info(f"通知: {rule.message}")
            except Exception as e:
                self._logger.error(f"告警规则检查失败: {rule.name}: {e}")

        return triggered

    def get_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """获取告警历史"""
        return list(self._history)[-limit:]

    def get_default_rules(self) -> List[AlertRule]:
        """获取默认告警规则"""
        return [
            AlertRule(
                name="high_error_rate",
                condition=lambda m: m.get("summary", {}).get("overall_error_rate", 0) > 10,
                message="错误率超过10%",
                severity="warning",
            ),
            AlertRule(
                name="critical_error_rate",
                condition=lambda m: m.get("summary", {}).get("overall_error_rate", 0) > 50,
                message="错误率超过50%，服务可能异常",
                severity="critical",
            ),
            AlertRule(
                name="high_memory_usage",
                condition=lambda m: m.get("system", {}).get("memory_rss_mb", 0) > 500,
                message="内存使用超过500MB",
                severity="warning",
            ),
            AlertRule(
                name="high_disk_usage",
                condition=lambda m: m.get("system", {}).get("disk_percent", 0) > 90,
                message="磁盘使用率超过90%",
                severity="critical",
            ),
        ]


# 单例
_metrics: Optional[MetricsCollector] = None
_health: Optional[HealthChecker] = None
_alerts: Optional[AlertManager] = None


def get_metrics_collector() -> MetricsCollector:
    global _metrics
    if _metrics is None:
        _metrics = MetricsCollector()
    return _metrics


def get_health_checker() -> HealthChecker:
    global _health
    if _health is None:
        _health = HealthChecker()
    return _health


def get_alert_manager() -> AlertManager:
    global _alerts
    if _alerts is None:
        _alerts = AlertManager()
        for rule in _alerts.get_default_rules():
            _alerts.add_rule(rule)
    return _alerts