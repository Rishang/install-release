import logging

# pipi
import typer

# locals
from InstallRelease.utils import rprint, logger
from InstallRelease.cli_interact import (
    GithubInfo,
    get as _get,
    upgrade as _upgrade,
    remove,
    list_installed,
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

app = typer.Typer(help=f"Github Release Installer, based on your system")


@app.command()
def get(
    debug: bool = __optionDebug,
    url: str = typer.Argument(None, help="[URL] of github repository "),
    tag_name: str = typer.Option("", "-t", help="get a specific tag version."),
    name: str = typer.Option("", "-n", help="tool name you want, Only for releases having different tools in releases")
):
    """
    | Install github release, cli tool
    """
    if debug:
        logger.setLevel(logging.DEBUG)

    if url is None or url == "":
        see_help("get")

    _get(GithubInfo(url), tag_name=tag_name, prompt=True, name=name)


@app.command()
def upgrade(
    debug: bool = __optionDebug,
):
    """
    | Upgrade all installed release, cli tools
    """
    if debug:
        logger.setLevel(logging.DEBUG)
    _upgrade()


@app.command()
def ls():
    """
    | list all installed release, cli tools
    """
    list_installed()


@app.command()
def rm(
    name: str = typer.Argument(None, help="name of installed tool to remove"),
    debug: bool = __optionDebug,
):
    """
    | remove any installed release, cli tools
    """
    if debug:
        logger.setLevel(logging.DEBUG)

    remove(name)


if __name__ == "__main__":
    app()
