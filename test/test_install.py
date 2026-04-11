#!/usr/bin/env python3
import subprocess
import yaml
import pytest


CONTAINER = "ir-ubuntu"


def load_config() -> dict:
    """Load test repos from asset.yml."""
    with open("./asset.yml", "r") as f:
        return yaml.safe_load(f)


def docker_exec(container: str, cmd: str):
    """Run a command inside the Docker container."""
    command = f'docker exec -i {container} bash -c "{cmd}"'
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    return result.stdout, result.stderr, result.returncode


def _is_container_running(name: str) -> bool:
    """Check if a Docker container is running."""
    result = subprocess.run(
        ["docker", "inspect", "-f", "{{.State.Running}}", name],
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() == "true"


@pytest.fixture(scope="session", autouse=True)
def ensure_container():
    """Ensure the Docker test container is running before tests."""
    if not _is_container_running(CONTAINER):
        subprocess.run(["bash", "setup.sh", "ubuntu"], check=True)
    assert _is_container_running(CONTAINER), f"Container '{CONTAINER}' is not running"


data = load_config()


@pytest.mark.parametrize("repo", data["repos"], ids=[r["name"] for r in data["repos"]])
def test_get(repo):
    """Install a tool and validate it runs correctly."""
    # Install
    stdout, stderr, rc = docker_exec(CONTAINER, repo["cmd"])
    print(stdout)

    # Validate
    validate_cmd = (
        f"{repo['validate']['cmd']} 2>&1 | grep -i '{repo['validate']['grep']}'"
    )
    stdout, stderr, rc = docker_exec(CONTAINER, validate_cmd)

    assert rc == 0, (
        f"Validation failed for {repo['name']}: stdout={stdout}, stderr={stderr}"
    )
    print(f"Validation passed for {repo['name']}")
