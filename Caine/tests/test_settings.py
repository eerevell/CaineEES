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
observer:
  internet_probe_host: 1.1.1.1
  internet_probe_port: 53
  internet_timeout_seconds: 5
reasoning:
  local_model_name: local
  remote_api_url: http://remote/reason
  remote_timeout_seconds: 6
  complexity_threshold: 7
update:
  repository_url: git@example.com:caine.git
  branch: main
  current_dir: /opt/caine-current
  update_dir: /opt/caine-update
  symlink_path: /opt/caine
  check_interval_seconds: 8
  requirements_file: requirements.txt
  test_command: [python, -m, pytest]
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
    assert settings.update.test_command == ["python", "-m", "pytest"]

