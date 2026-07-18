"""Tests for YAML settings."""

from __future__ import annotations

from Caine.config.settings import load_settings


def test_load_settings(tmp_path) -> None:
    config = tmp_path / "caine.yaml"
    config.write_text(
        """
memory:
  data_dir: /var/lib/caine
  sqlite_file: caine.sqlite3
  checkpoint_file: checkpoint.json
runtime:
  loop_interval_seconds: 1
  checkpoint_interval_seconds: 2
  max_consecutive_failures: 3
  shutdown_timeout_seconds: 4
  watchdog_timeout_seconds: 9
observer:
  internet_probe_host: 1.1.1.1
  internet_probe_port: 53
  internet_timeout_seconds: 5
  systemd_services: [caine.service]
reasoning:
  local_model_name: local
  remote_api_url: http://remote/reason
  remote_timeout_seconds: 6
  complexity_threshold: 7
network:
  remote_node_name: EES2
  heartbeat_url: http://remote/health
  heartbeat_interval_seconds: 10
  reconnect_backoff_seconds: 11
  max_reconnect_backoff_seconds: 12
update:
  repository_url: git@example.com:caine.git
  branch: main
  current_dir: /opt/caine-current
  update_dir: /opt/caine-update
  symlink_path: /opt/caine
  check_interval_seconds: 8
  requirements_file: requirements.txt
  test_command: [python, -m, pytest]
  startup_probe_command: [python, -m, pytest, Caine/tests/test_settings.py]
  metadata_file: /var/lib/caine/version.json
logging:
  level: INFO
  file_path: /var/log/caine/caine.log
plugins:
  enabled: true
  directories: [/opt/caine/plugins]
""",
        encoding="utf-8",
    )

    settings = load_settings(config)

    assert settings.runtime.loop_interval_seconds == 1
    assert settings.observer.internet_probe_host == "1.1.1.1"
    assert settings.network.remote_node_name == "EES2"
    assert settings.update.test_command == ["python", "-m", "pytest"]
