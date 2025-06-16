import os
import re
import sys
import json
import shutil
import logging
import platform
import subprocess
import dataclasses
from pathlib import Path
from typing import List, Dict
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
from importlib.metadata import version, PackageNotFoundError

# pipi
import requests
from rich import print as pprint
from rich.console import Console
from rich.logging import RichHandler
from rich.text import Text
from rich.table import Table

try:
    from magic.compat import detect_from_filename
except ImportError:
    pprint(
        "[red]Failed to find libmagic.  Check your installation\n"
        "refer this url to install libmagic first: https://github.com/ahupp/python-magic#installation [/]"
    )
    sys.exit(1)

# logging.basicConfig(level=logging.INFO)


# locals
from InstallRelease.constants import _colors

requests_session = requests.Session()

console = Console()


def _logger(flag: str = "", format: str = ""):
    if format == "" or format is None:
        format = "%(levelname)s|%(name)s| %(message)s"

    # message
    logger = logging.getLogger(__name__)

    if os.environ.get(flag) is not None:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)

    # create console handler and set level to debug
    # ch = logging.StreamHandler()
    # ch.setLevel(logging.DEBUG)
    # # create formatter
    # # add formatter to ch
    # formatter = logging.Formatter(format)
    # ch.setFormatter(formatter)

    # # add ch to logger
    # logger.addHandler(ch)
    handler = RichHandler(log_time_format="")
    logger.addHandler(handler)
    return logger


# message
# export LOG_LEVEL=true
logger = _logger("LOG_LEVEL")


class EnhancedJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if dataclasses.is_dataclass(o):
            return dataclasses.asdict(o)
        return super().default(o)


class PackageVersion:
    def __init__(self, package_name: str):
        self.package_name = package_name
        self.url = f"https://pypi.org/pypi/{package_name}/json"
        self._local_version = self.local_version()
        self._latest_version = None

    def local_version(self):
        try:
            _version = version(self.package_name)
            return _version
        except PackageNotFoundError:
            return None

    def latest_version(self):
        try:
            if self._latest_version is not None:
                return self._latest_version

            response = requests_session.get(self.url)
            logger.debug(
                f"pipi response for package '{self.package_name}': " + str(response)
            )
            data = response.json()
            version = data["info"]["version"]
            self._latest_version = version

            return version

        except requests.RequestException:
            print(f"Failed to fetch data for {self.package_name}")
            return None


def FilterDataclass(data: dict, obj):
    """"""

    out: dict = dict()
    names = set([f.name for f in dataclasses.fields(obj)])
    for k, v in data.items():
        if k in names:
            out[k] = v
    return obj(**out)


def is_none(val):
    if val is None:
        return True
    elif isinstance(val, str) and val != "":
        return False
    elif isinstance(val, dict) and val != {}:
        return False
    elif isinstance(val, list) and val != []:
        return False
    return True


@dataclass
class ShellOutputs:
    stdout: List[str]
    stderr: List[str]
    returncode: int


class Shell:
    line_breaks = "\n"
    popen_args = {"shell": True, "stdout": subprocess.PIPE, "stderr": subprocess.PIPE}

    def console_to_str(self, s):
        console_encoding = sys.__stdout__.encoding

        """ From pypa/pip project, pip.backwardwardcompat. License MIT. """
        if s is None:
            return
        try:
            return s.decode(console_encoding, "ignore")
        except UnicodeDecodeError:
            return s.decode("utf_8", "ignore")

    def str_from_console(self, s):
        text_type = str

        try:
            return text_type(s)
        except UnicodeDecodeError:
            return text_type(s, encoding="utf_8")

    def cmd(self, cmd) -> ShellOutputs:
        try:
            process = subprocess.Popen(cmd, **self.popen_args)  # type: ignore
            stdout, stderr = process.communicate()
            returncode = process.returncode

        except Exception as e:
            logger.error("Exception for %s: \n%s" % (subprocess.list2cmdline(cmd), e))

        returncode = returncode

        stdout = self.console_to_str(stdout)
        stdout = stdout.split(self.line_breaks)
        stdout = list(filter(None, stdout))  # filter empty values

        stderr = self.console_to_str(stderr)
        stderr = stderr.split(self.line_breaks)
        stderr = list(filter(None, stderr))  # filter empty values

        if "has-session" in cmd and len(stderr):
            if not stdout:
                stdout = stderr[0]
        logger.debug(f"stdout for {cmd}:\n{stdout}")

        return ShellOutputs(stdout=stdout, stderr=stderr, returncode=returncode)


def sh(command: str):
    s = Shell()
    return s.cmd(command)


def mkdir(path: str):
    file_path = Path(path)
    file_path = file_path.expanduser()

    if not file_path.is_dir():
        logger.debug(f"creating dir: {file_path.absolute()}")
        os.makedirs(name=file_path.absolute())
    else:
        ...


def download(url: str, at: str):
    """Download a file"""

    file = requests_session.get(url, stream=True)
    if not os.path.exists(at):
        os.makedirs(at)

    file_name: str = url.split("/")[-1]
    if file.status_code == 200:
        with open(f"{at}/{file_name}", "wb") as fw:
            fw.write(file.content)
        logger.info(f"""Downloaded: \'{file_name}\' at {at}""")
        return f"{at}/{file_name}"
    else:
        logger.info(f"url: {url}, status_code: {file.status_code}")
        exit()


def extract(path: str, at: str):
    """Extract tar file"""

    try:
        system = platform.system().lower()
        file_info = detect_from_filename(path)

        if file_info.mime_type == "application/x-7z-compressed":
            if system in ["linux"]:
                cmd = f"7z x {path} -o{at}"
                logger.debug("command: " + cmd)
                sh(cmd)
            elif system == "windows":
                # 'C:\Program Files\\7-zip\\7z.exe'
                ...
        elif file_info.mime_type == "application/x-bzip2" or path.endswith(
            (".bz2", ".tbz")
        ):
            import bz2
            import tarfile

            logger.debug(f"Extracting bzip2 file: {path}")
            if path.endswith(".bz2") and not path.endswith(".tar.bz2"):
                # Single file compressed with bz2
                with bz2.open(path, "rb") as f_in:
                    output_file = os.path.join(at, os.path.basename(path)[:-4])
                    with open(output_file, "wb") as f_out:
                        f_out.write(f_in.read())
            else:
                # Tar archive compressed with bz2
                with tarfile.open(path, "r:bz2") as tar:
                    tar.extractall(path=at)
        else:
            shutil.unpack_archive(path, at)

        return True
    except Exception as e:
        logger.error(f"can't extract: {path}, error: {e}")
        raise Exception("Invalid file")


def listItemsMatcher(patterns: List[str], word: str) -> float:
    """
    eg: listItemsMatcher(patterns=['a','b'], word='a-cc') --> 0.5
    """

    count = 0

    for pattern in patterns:
        if re.search(pattern.lower(), word.lower()):
            count += 1

    if count == 0:
        return 0

    return count / len(patterns)


def threads(funct, data, max_workers=5, return_result: bool = True):
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future = executor.map(funct, data)
        if return_result is True:
            for i in future:
                results.append(i)
    return results


def show_table(
    data: List[Dict], ignore_keys: List = [], title: str = "", border_style=""
):
    """rich table"""

    def dict_list_tbl(items=List[dict], ignore_keys: list = []):
        keys = []
        data = []

        for item in items:
            _tmp: tuple = ()
            for key in [i for i in item.keys() if i not in ignore_keys]:
                if key not in keys:
                    keys.append(key)
                _tmp += (str(item[key]),)
            data.append(_tmp)

        return keys, data

    text = Text(title, style=_colors["light_green"])

    print()

    table = Table(title=text, style=_colors["purple"], border_style=border_style)
    columns, rows = dict_list_tbl(data, ignore_keys)

    colors = {
        0: _colors["yellow"],
        1: _colors["red"],
        2: _colors["green"],
        3: _colors["cyan"],
        4: _colors["blue"],
    }

    for count, col in enumerate(columns):
        color = colors[count % len(colors)]
        table.add_column(col, justify="left", style=color, no_wrap=True)
    for row in rows:
        table.add_row(*row)

    console = Console()
    console.print(table)
