import logging

# pipi
import typer

# locals
from src.utils import rprint, logger
from src.cli_interact import (
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

app = typer.Typer(help=f"release Installer")


@app.command()
def get(
    debug: bool = __optionDebug,
    url: str = typer.Argument(None, help="[URL] of github repository "),
):
    """
    | Install github release, cli tool
    """
    if debug:
        logger.setLevel(logging.DEBUG)

    if url is None or url == "":
        see_help("get")
    repo = GithubInfo(url)
    _get(repo, prompt=True)


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
