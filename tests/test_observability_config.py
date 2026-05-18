from __future__ import annotations

import json
from pathlib import Path
from typing import cast

ROOT_DIR = Path(__file__).resolve().parents[1]
PROMETHEUS_CONFIG = ROOT_DIR / "observability" / "prometheus" / "prometheus.yml"
GRAFANA_DATASOURCE = (
    ROOT_DIR
    / "observability"
    / "grafana"
    / "provisioning"
    / "datasources"
    / "prometheus.yml"
)
GRAFANA_DASHBOARD_PROVIDER = (
    ROOT_DIR
    / "observability"
    / "grafana"
    / "provisioning"
    / "dashboards"
    / "job-runner-platform.yml"
)
GRAFANA_DASHBOARD = (
    ROOT_DIR / "observability" / "grafana" / "dashboards" / "job-runner-platform.json"
)


def test_prometheus_config_scrapes_api_and_worker_metrics() -> None:
    config = PROMETHEUS_CONFIG.read_text(encoding="utf-8")

    assert "job_name: job-runner-api" in config
    assert 'targets: ["api:8000"]' in config
    assert "job_name: job-runner-worker" in config
    assert 'targets: ["worker:8001"]' in config
    assert "metrics_path: /metrics" in config


def test_grafana_provisioning_uses_local_prometheus_and_dashboard() -> None:
    datasource = GRAFANA_DATASOURCE.read_text(encoding="utf-8")
    provider = GRAFANA_DASHBOARD_PROVIDER.read_text(encoding="utf-8")

    assert "name: Prometheus" in datasource
    assert "uid: prometheus" in datasource
    assert "url: http://prometheus:9090" in datasource
    assert "path: /etc/grafana/dashboards" in provider


def test_grafana_dashboard_has_core_job_api_and_worker_panels() -> None:
    dashboard = json.loads(GRAFANA_DASHBOARD.read_text(encoding="utf-8"))

    assert dashboard["title"] == "Job Runner Platform"
    assert dashboard["uid"] == "job-runner-platform"
    panels = cast(list[dict[str, object]], dashboard["panels"])
    assert len(panels) >= 4

    expressions: set[str] = set()
    for panel in panels:
        targets = cast(list[dict[str, object]], panel.get("targets", []))
        for target in targets:
            expr = target.get("expr")
            if isinstance(expr, str):
                expressions.add(expr)

    assert "sum(jobs_created_total)" in expressions
    assert (
        "sum by (method, path, status_code) "
        "(rate(api_requests_total[5m]))" in expressions
    )
    assert "sum by (outcome) (rate(worker_polls_total[5m]))" in expressions
    assert (
        "histogram_quantile(0.95, sum by (le) "
        "(rate(job_duration_seconds_bucket[5m])))" in expressions
    )


def test_docker_compose_mounts_observability_configuration() -> None:
    compose = (ROOT_DIR / "docker-compose.yml").read_text(encoding="utf-8")

    assert (
        "./observability/prometheus/prometheus.yml:"
        "/etc/prometheus/prometheus.yml:ro" in compose
    )
    assert (
        "./observability/grafana/provisioning:/etc/grafana/provisioning:ro" in compose
    )
    assert "./observability/grafana/dashboards:/etc/grafana/dashboards:ro" in compose
    assert 'JOB_RUNNER_WORKER_METRICS_ENABLED: "true"' in compose
    assert 'JOB_RUNNER_WORKER_METRICS_PORT: "8001"' in compose
    assert 'GF_AUTH_ANONYMOUS_ENABLED: "true"' in compose
