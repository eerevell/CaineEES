# Caine

Caine is a modular autonomous Python runtime designed to run continuously on
Debian 12 after an initial setup step. It is not an operating system and does
not reimplement operating-system services. Instead, it relies on Debian-native
components such as systemd, journalctl, SQLite, git, ssh, and networkd.

The project is intentionally structured as a production-ready foundation rather
than a quick prototype. The code is typed, split into focused modules, tested,
and prepared for growth into a larger autonomous system.

## Goals

- Run indefinitely as a systemd service.
- Make operational decisions without user interaction after setup.
- Keep EES1 as the only Caine organism.
- Treat EES2 only as a remote compute coprocessor.
- Persist memory and checkpoints outside the source tree.
- Recover after crashes using the last saved checkpoint.
- Update itself through Git only after dependencies install and tests pass.
- Continue operating when the remote model server is unavailable.
- Allow plugins to add capabilities without changing the core.

## Architecture

`Brain` is the coordinator. It does not contain business logic. The rest of the
runtime is injected into it as independent components:

- `Planner` creates goals and manages task priority.
- `Observer` reads CPU, RAM, disk, temperature, internet, and module health.
- `Executor` dispatches tasks to registered async handlers.
- `Critic` validates task results and limits repeated failure loops.
- `Reasoning` routes simple decisions locally and complex ones remotely.
- `MemoryStore` persists knowledge, history, goals, errors, and experience.
- `Scheduler` runs periodic jobs such as checkpoints and update checks.
- `Updater` performs Git-based self-updates through a staging directory.
- `StartupManager` restores durable state.
- `ShutdownManager` handles SIGTERM and SIGINT gracefully.
- `PluginRegistry` loads external task handlers.
- `EventBus` decouples modules through asynchronous events.
- `HealthManager` checks and recovers unhealthy components.
- `Watchdog` detects stale modules and restarts only affected components.

## EES1 and EES2 Roles

Caine has one organism only: EES1.

EES1 owns:

- Brain;
- Planner;
- Memory;
- Observer;
- Executor;
- Critic;
- Scheduler;
- Reasoning;
- Updater;
- Shutdown;
- all goals, history, checkpoints, and decisions.

EES2 is not another Caine instance. It has no Brain, no persistent memory, and
no independent decision loop. It is a compute-only node used by EES1 for tasks
such as LLM inference over HTTP.

The architecture is built so additional compute nodes can be added later
without splitting Caine into multiple organisms.

## Main Loop

Each cycle performs the same high-level sequence:

1. Check system state.
2. Check memory.
3. Check the task queue.
4. Determine the next goal.
5. Execute the selected task.
6. Critique the result.
7. Record experience.
8. Save periodic checkpoints.

The loop is asynchronous and intended to run forever under systemd supervision.
Events are published through `EventBus` during cycle start, decisions, task
completion, remote-node state changes, shutdown, and watchdog recovery.

## Project Layout

```text
Caine/
  core/
    brain.py
    planner.py
    observer.py
    executor.py
    critic.py
    scheduler.py
    reasoning.py
    updater.py
    shutdown.py
    startup.py
  memory/
    store.py
  network/
    compute_node.py
    remote_reasoning.py
  plugins/
    registry.py
  config/
    caine.yaml
    settings.py
  systemd/
    caine.service
  scripts/
    install_debian12.sh
    run_tests.sh
  tests/
caine.py
requirements.txt
README.md
```

## Persistence

By default, durable state is stored in `/var/lib/caine`:

- SQLite database: `/var/lib/caine/caine.sqlite3`
- Checkpoint file: `/var/lib/caine/checkpoint.json`

The database schema includes tasks, goals, memories, experiences, and errors.
The memory location is intentionally outside the source tree so updates do not
destroy operational history.

## Configuration

All runtime values live in YAML:

```text
Caine/config/caine.yaml
```

For a real deployment, copy it to:

```text
/etc/caine/caine.yaml
```

Important settings include:

- memory paths;
- loop and checkpoint intervals;
- remote reasoning API URL;
- remote compute node heartbeat URL;
- Git repository and branch;
- update directories;
- test command;
- logging path;
- plugin directories.

## Debian 12 Installation

Install Python 3.12, git, and systemd support packages on Debian 12. Then place
the project in `/opt/caine-current` and point `/opt/caine` at it:

```bash
sudo useradd --system --home /var/lib/caine --shell /usr/sbin/nologin caine
sudo mkdir -p /opt/caine-current
sudo ln -sfn /opt/caine-current /opt/caine
sudo bash Caine/scripts/install_debian12.sh
```

After installation:

```bash
sudo systemctl status caine
sudo journalctl -u caine -f
```

## systemd

The service unit is located at:

```text
Caine/systemd/caine.service
```

It starts Caine after network-online, restarts it on failure, sends SIGTERM on
shutdown, and writes stdout/stderr to the journal.

## Self-Updates

Caine checks for updates on the configured interval. The default model is:

```text
/opt/caine-current   active release tree
/opt/caine-update    candidate update tree
/opt/caine           symlink to active tree
```

The updater:

1. Fetches or clones the configured branch.
2. Installs dependencies if `requirements.txt` exists.
3. Runs the configured test command.
4. Runs a startup probe command.
5. Switches the symlink only if validation passes.
6. Stores current and previous version metadata.
7. Rolls back to the previous target when anything fails.

## Remote Reasoning

Caine can use a second machine as a compute server for larger language models.
Communication is HTTP-based. If the server is offline, Caine falls back to local
decision logic and continues running.

EES1 checks EES2 with heartbeat requests. When EES2 becomes unavailable,
Reasoning automatically stays local. When heartbeat recovers, remote inference
is used again for sufficiently complex prompts.

Expected remote response shape:

```json
{
  "answer": "decision text"
}
```

## Plugins

Plugins are Python files from configured plugin directories. A plugin exposes a
`plugin` object:

```python
class ExamplePlugin:
    name = "example"
    permissions = {"executor.register"}

    async def on_load(self):
        ...

    async def on_start(self):
        ...

    async def on_tick(self):
        ...

    async def on_stop(self):
        ...

    async def on_unload(self):
        ...

    def event_subscriptions(self):
        return {"task.finished": "on_task_finished"}

    async def register(self, executor):
        executor.handlers["example_task"] = handler


plugin = ExamplePlugin()
```

This lets new task handlers and event subscribers be added without modifying
the core runtime. The registry tracks plugin permissions for future sandboxing
and policy enforcement.

## Health and Watchdog

`HealthManager` tracks:

- Brain;
- Memory;
- SQLite;
- Network;
- Updater;
- Scheduler;
- Remote Node.

When a component reports unhealthy state, the manager attempts the registered
recovery action. `Watchdog` separately tracks component responsiveness and can
restart only the stale component instead of stopping the whole organism.

## Checkpoints

Checkpoints include:

- current goal;
- task queue;
- planner state;
- memory state;
- save timestamp.

Startup restores the latest checkpoint and merges it with pending durable tasks
from SQLite.

## Development

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

Run tests:

```bash
python -m pytest Caine/tests
```

Current verification status:

```text
16 passed
```

## Status

This repository contains the production-oriented foundation for Caine:

- autonomous runtime loop;
- SQLite memory;
- checkpoint and recovery;
- systemd integration;
- self-update mechanism;
- graceful shutdown;
- plugin loading;
- EventBus;
- HealthManager;
- Watchdog;
- local/remote reasoning router;
- EES1/EES2 role separation;
- focused test suite.

The next engineering step is to add real task handlers for concrete operational
goals: Debian maintenance, network diagnostics, SSH workflows, model-server
health checks, and richer local reasoning backends.
