#!/usr/bin/env python3
from InstallRelease.utils import sh
import yaml
import os


def load_config() -> dict:
    with open("./asset.yml", "r") as f:
        return yaml.safe_load(f)


def docker_exec(container: str, cmd: str):
    command = f'docker exec -it {container} bash -c "{cmd}"'
    out = sh(command)
    return "\n".join(out.stdout), "\n".join(out.stderr), out.returncode


os.system("docker rm -f ir-ubuntu; task test -- ubuntu")
container = "ir-ubuntu"
data = load_config()


def test_get(name: str = "all!"):
    failed_repos = []
    if name == "all!":
        repos = data["repos"]
    else:
        repos = [repo for repo in data["repos"] if repo["name"] == name]

    for repo in repos:
        cmd = repo["cmd"]
        out = docker_exec(container, cmd)
        print(out[0])
        validate_cmd = (
            f"{repo['validate']['cmd']} 2>&1 | grep -i '{repo['validate']['grep']}'"
        )
        print("Validate command:")
        print(validate_cmd)
        validate = docker_exec(container, validate_cmd)

        if validate[2] != 0:
            print(
                f"Validation failed for {repo['name']} with return code {validate[2]}"
            )
            print(validate[1])
            failed_repos.append((repo["name"], validate[0], validate[1], validate[2]))
        else:
            print(f"Validation passed for {repo['name']}")

    assert len(failed_repos) == 0, f"Failed repos: {failed_repos}"
    print(f"All tests passed for {name}")


test_get()
