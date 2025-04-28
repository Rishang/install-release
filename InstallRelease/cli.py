import logging
import os
from typing import Optional

# pipi
import typer

# locals
from InstallRelease.utils import pprint, logger
from InstallRelease.cli_interact import (
    pull_state,
    get as _get,
    upgrade as _upgrade,
    remove,
    list_install,
    show_state,
    hold,
    cache_config,
    config,
    install_release_version,
)
from InstallRelease.core import get_repo_info


def see_help(arg: str = ""):
    pprint(
        f"This command required arguments, use [yellow]{arg} --help[reset] to see them"
    )
    exit(1)


# cli debug type alias
__optionDebug = typer.Option(False, "-v", help="set verbose mode.")
__optionQuite = typer.Option(False, "-q", help="set quite mode.")
__optionForce = typer.Option(False, "-F", help="set force.")
__optionSkipPrompt = typer.Option(False, "-y", help="skip confirmation (y/n) prompt.")


def setLogger(quite: Optional[bool] = None, debug: Optional[bool] = None) -> None:
    """Set logger level based on verbosity options

    Args:
        quite: Enable quiet mode (fewer messages)
        debug: Enable debug mode (more messages)
    """
    if debug:
        logger.setLevel(logging.DEBUG)
    elif quite:
        logger.setLevel(logging.ERROR)


if os.environ.get("IR_DEBUG", "").lower() == "true":
    setLogger(debug=True)

app = typer.Typer(help="GitHub/GitLab Release Installer, based on your system")


@app.command()
def get(
    debug: bool = __optionDebug,
    quite: bool = __optionQuite,
    url: str = typer.Argument(None, help="[URL] of GitHub/GitLab repository"),
    tag_name: str = typer.Option("", "-t", help="get a specific tag version."),
    name: str = typer.Option(
        "",
        "-n",
        help="tool name you want, Only for releases having different tools in releases",
    ),
    approve: bool = typer.Option(False, "-y", help="Approve without Prompt"),
):
    """
    | Install GitHub/GitLab release, cli tool
    """

    setLogger(quite, debug)
    if url is None or url == "":
        see_help("get")

    _url = url
    url = "/".join(_url.split("/")[:5])

    repo = get_repo_info(url, token=config.token, gitlab_token=config.gitlab_token)

    _get(
        repo,
        tag_name=tag_name,
        prompt=not approve,
        name=name,
    )


@app.command()
def upgrade(
    debug: bool = __optionDebug,
    quite: bool = __optionQuite,
    force: bool = __optionForce,
    skip_prompt: bool = __optionSkipPrompt,
):
    """
    | Upgrade all installed release, cli tools
    """
    setLogger(quite, debug)
    local_version = install_release_version.local_version()
    latest_version = install_release_version.latest_version()
    logger.debug(f"local_version: {local_version}")
    logger.debug(f"latest_version: {latest_version}")
    # if local_version != latest_version:
    #     pprint(
    #         "[bold]***INFO: New version of install-release is available, "
    #         "run [yellow]ir me --upgrade[reset] to update. ***\n"
    #     )
    _upgrade(force=force, skip_prompt=skip_prompt)


@app.command()
def ls(
    hold: bool = typer.Option(
        False,
        "--hold",
        help="list of tools which are kept on hold",
    ),
):
    """
    | List all installed releases, cli tools
    """
    list_install(hold_update=hold)


@app.command()
def rm(
    name: str = typer.Argument(None, help="name of installed tool to remove"),
    debug: bool = __optionDebug,
):
    """
    | Remove any installed releases, cli tools
    """
    setLogger(debug=debug)

    remove(name)


@app.command(name="config")
def _config(
    debug: bool = __optionDebug,
    token: str = typer.Option(
        "",
        "--token",
        help="set your GitHub token to solve API rate-limiting issue",
    ),
    gitlab_token: str = typer.Option(
        "",
        "--gitlab-token",
        help="set your GitLab token to solve API rate-limiting issue",
    ),
    path: str = typer.Option(
        "",
        "--path",
        help="set install path",
    ),
    pre_release: bool = typer.Option(
        False, "--pre-release", help="Also include pre-releases while checking updates."
    ),
):
    """
    | Set configs for tool
    """

    setLogger(debug=debug)

    logger.info(f"Loading config: {cache_config.state_file}")

    if token != "":
        config.token = token
        logger.info("Updated GitHub token")
    if gitlab_token != "":
        config.gitlab_token = gitlab_token
        logger.info("Updated GitLab token")
    if path != "":
        config.path = path
        logger.info(f"Updated path to {path}")

    config.pre_release = pre_release

    cache_config.save()
    logger.info("Done.")


@app.command()
def state(debug: bool = __optionDebug):
    """
    | Show the current stored state
    """
    setLogger(debug=debug)
    show_state()


@app.command()
def pull(
    debug: bool = __optionDebug,
    url: str = typer.Option(
        "",
        "--url",
        help="install tools from the remote state",
    ),
    override: bool = typer.Option(
        False,
        "-O",
        help="Enable Override local tool version with remote state version.",
    ),
):
    """
    | Install tools from the remote state
    """
    setLogger(debug=debug)

    if url is None or url == "":
        see_help("pull")

    pull_state(url, override)


@app.command(name="hold")
def _hold(
    name: str = typer.Argument(
        None, help="Name of tool for which updates will be kept on hold"
    ),
    unset: bool = typer.Option(True, "--unset", help="unset from hold."),
):
    """
    | Keep updates a tool on hold.
    """
    hold(name, hold_update=unset)


@app.command(name="me")
def me(
    update: bool = typer.Option(
        False, "--upgrade", "-U", help="Update tool, install-release."
    ),
    version: bool = typer.Option(
        False, "--version", help="print version this tool, install-release."
    ),
):
    """
    | Update install-release tool.
    """

    _v = install_release_version._local_version

    if update:
        _cmd = "ir get https://github.com/Rishang/install-release"
        pprint(f"Running: {_cmd}")

        os.system(_cmd)
        pprint(
            "\n\nNote: If update failed, with message `[red]error: externally-managed-environment[reset]` "
            "then try running below command,\n"
            f"command: [yellow]{_cmd} --break-system-packages[reset]"
        )
    elif version:
        pprint(_v)
    else:
        pprint(f"Version: {_v}")
        pprint("Repo:    https://github.com/Rishang/install-release")


if __name__ == "__main__":
    app()
