"""Command-line interface and runtime composition for Release Rat."""

import argparse
import os
from pathlib import Path
import sqlite3
import sys
import time
from collections.abc import Callable
from typing import TextIO

from .config import AppConfig, ConfigError, load_config
from .delivery import DeliveryRouter
from .github import GitHubClient
from .judgment import FallbackJudge, HeuristicJudge, OpenAICompatibleJudge
from .runner import ReleaseRat, RunSummary
from .state import StateStore


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line options and select exactly one run mode."""
    parser = argparse.ArgumentParser(description="Monitor configured GitHub releases.")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--once", action="store_true", help="run one normal poll")
    modes.add_argument("--watch", action="store_true", help="poll repeatedly")
    modes.add_argument(
        "--backfill",
        action="store_true",
        help="run one poll that also processes baseline releases",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config.json"),
        help="path to the JSON configuration file (default: config.json)",
    )
    args = parser.parse_args(argv)
    args.once = not args.watch and not args.backfill
    return args


def build_release_rat(config: AppConfig, state: StateStore) -> ReleaseRat:
    """Build the production collaborators for one configured worker."""
    github = GitHubClient(token=os.getenv(config.github_token_env))
    fallback = HeuristicJudge()
    if config.llm.enabled and os.getenv(config.llm.api_key_env):
        judge = FallbackJudge(OpenAICompatibleJudge(config.llm), fallback)
    else:
        judge = fallback
    delivery = DeliveryRouter(
        webhook_url=os.getenv(config.discord_webhook_env),
        log_path=config.local_log_path,
    )
    return ReleaseRat(config, github, state, judge, delivery)


def _print_summary(summary: RunSummary, output: TextIO) -> None:
    print(
        "Run complete: "
        f"fetched={summary.fetched} seeded={summary.seeded} "
        f"judged={summary.judged} reported={summary.reported} "
        f"ignored={summary.ignored} errors={summary.errors} "
        f"repository_errors={summary.repository_errors}",
        file=output,
    )


def _watch(
    rat: ReleaseRat,
    poll_interval_seconds: int,
    sleeper: Callable[[float], None],
    output: TextIO,
) -> None:
    while True:
        _print_summary(rat.poll("normal"), output)
        sleeper(poll_interval_seconds)


def main(
    argv: list[str] | None = None,
    *,
    sleeper: Callable[[float], None] = time.sleep,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    """Run Release Rat and return a process-compatible exit code."""
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    args = parse_args(argv)
    try:
        config = load_config(args.config)
        config.state_path.parent.mkdir(parents=True, exist_ok=True)
        config.local_log_path.parent.mkdir(parents=True, exist_ok=True)
        with StateStore(config.state_path) as state:
            rat = build_release_rat(config, state)
            if args.watch:
                _watch(rat, config.poll_interval_seconds, sleeper, stdout)
            else:
                mode = "backfill" if args.backfill else "normal"
                _print_summary(rat.poll(mode), stdout)
        return 0
    except KeyboardInterrupt:
        return 0
    except (ConfigError, OSError, sqlite3.Error) as exc:
        print(f"configuration/state initialization failed: {exc}", file=stderr)
        return 1
