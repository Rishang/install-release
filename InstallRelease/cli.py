import logging
import os

# pipi
import typer

# locals
from InstallRelease.utils import rprint, logger
from InstallRelease.cli_interact import (
    GithubInfo,
    pull_state,
    get as _get,
    upgrade as _upgrade,
    remove,
    list_install,
    show_state,
    hold,
    cache_config,
    config,
)


def see_help(arg: str = ""):
    rprint(
        "This command required arguments, use "
        f"[yellow]{arg} --help[reset]"
        " to see them"
    )
    exit(1)


# cli debug type alias
__optionDebug = typer.Option(False, "-v", help="set verbose mode.")
__optionQuite = typer.Option(False, "-q", help="set quite mode.")
__optionForce = typer.Option(False, "-F", help="set force.")


def setLogger(quite: bool = None, debug: bool = None):
    if debug:
        logger.setLevel(logging.DEBUG)
    elif quite:
        logger.setLevel(logging.ERROR)


if os.environ.get("IR_DEBUG", "").lower() == "true":
    setLogger(debug=True)

app = typer.Typer(help=f"Github Release Installer, based on your system")


@app.command()
def get(
    debug: bool = __optionDebug,
    quite: bool = __optionQuite,
    url: str = typer.Argument(None, help="[URL] of github repository "),
    tag_name: str = typer.Option("", "-t", help="get a specific tag version."),
    name: str = typer.Option(
        "",
        "-n",
        help="tool name you want, Only for releases having different tools in releases",
    ),
    approve: bool = typer.Option(False, "-y", help="Approve without Prompt"),
):
    """
    | Install github release, cli tool
    """

    setLogger(quite, debug)
    if url is None or url == "":
        see_help("get")

    _get(
        GithubInfo(url, token=config.token),
        tag_name=tag_name,
        prompt=not approve,
        name=name,
    )


@app.command()
def upgrade(
    debug: bool = __optionDebug,
    quite: bool = __optionQuite,
    force: bool = __optionForce,
):
    """
    | Upgrade all installed release, cli tools
    """
    setLogger(quite, debug)
    _upgrade(force=force)


@app.command()
def ls(
    hold: bool = typer.Option(
        False,
        "--hold",
        help="list of tools which are kept on hold",
    )
):
    """
    | list all installed release, cli tools
    """
    list_install(hold_update=hold)


@app.command()
def rm(
    name: str = typer.Argument(None, help="name of installed tool to remove"),
    debug: bool = __optionDebug,
):
    """
    | remove any installed release, cli tools
    """
    setLogger(debug=debug)

    remove(name)


@app.command(name="config")
def Config(
    debug: bool = __optionDebug,
    token: str = typer.Option(
        "",
        "--token",
        help="set your github token to solve github api rate-limiting issue",
    ),
    path: str = typer.Option(
        "",
        "--path",
        help="set install path",
    ),
):
    """
    | Set configs for tool
    """

    setLogger(debug=debug)

    logger.info(f"Loading config: {cache_config.state_file}")

    if token != "":
        config.token = token
        logger.info("Updated token")
    if path != "":
        config.path = path
        logger.info("Updated path")

    cache_config.save()
    logger.info("Done.")


@app.command()
def state(debug: bool = __optionDebug):
    """
    | show currnet stored state
    """
    setLogger(debug=debug)
    show_state()


@app.command()
def pull(
    debug: bool = __optionDebug,
    url: str = typer.Option(
        "",
        "--url",
        help="install tools from remote state",
    ),
    override: bool = typer.Option(
        False,
        "-O",
        help="Enable Override local tool version with remote state version.",
    ),
):
    """
    | Install tools from remote state
    """
    setLogger(debug=debug)

    if url is None or url == "":
        see_help("pull")

    pull_state(url, override)


@app.command()
def version():
    """
    | print version of install-release
    """
    import InstallRelease

    print(InstallRelease.__version__)


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


if __name__ == "__main__":
    app()
