import os
import re
import sys
import json
import logging
import platform
import subprocess
import dataclasses
from pathlib import Path
from typing import List, Dict
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
import urllib.parse

# pipi
import pkg_resources
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
            version = pkg_resources.get_distribution(self.package_name).version
            return version
        except pkg_resources.DistributionNotFound:
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


def download(url: str, at: str) -> str:
    """
    Download file to location
    """
    # Decode URL-encoded characters in the filename
    filename = os.path.basename(urllib.parse.unquote(url))

    # Remove query parameters if present
    if "?" in filename:
        filename = filename.split("?")[0]

    # Clean the filename to remove any remaining problematic characters
    filename = re.sub(r"[^\w\-\.]", "_", filename)

    filepath = f"{at}/{filename}"

    logger.debug(f"Downloading: {url}")
    logger.debug(f"To: {filepath}")

    # Use requests to download the file
    with requests_session.get(url, stream=True) as r:
        r.raise_for_status()
        with open(filepath, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)

    return filepath


def extract(path: str, at: str):
    """
    Extract a compressed file
    """
    logger.debug(f"Extraction input: {path}")

    exception_compressed_mime_type = [
        "application/x-7z-compressed",
    ]
    # Ensure the path is using decoded URL characters
    path = urllib.parse.unquote(path)
    file_info = detect_from_filename(path)
    system = platform.system().lower()

    try:
        # Handle tar.gz files
        if file_info.mime_type in [
            "application/gzip",
            "application/x-gzip",
        ] and path.endswith(".tar.gz"):
            logger.debug(f"Detected tar.gz file: {path}")
            if system == "linux" or system == "darwin":
                sh(f"tar -xf {path} -C {at}")
            else:
                logger.debug("System not supported for tar extraction")

        # Handle zip files
        elif file_info.mime_type == "application/zip":
            logger.debug(f"Detected zip file: {path}")
            if system == "linux" or system == "darwin":
                sh(f"unzip -o {path} -d {at}")
            else:
                logger.debug("System not supported for zip extraction")

        # Handle other archives
        elif file_info.mime_type in exception_compressed_mime_type:
            logger.debug(
                f"Detected compressed file: {path} with mime: {file_info.mime_type}"
            )
            if system == "linux" or system == "darwin":
                sh(f"7z x {path} -o{at}")
            else:
                logger.debug("System not supported for 7z extraction")
        else:
            logger.debug(f"Not an archive: {path} with mime: {file_info.mime_type}")
            return True

        return True
    except Exception as e:
        logger.error(f"can't extract: {path}, error: {e}")
        logger.debug(f"File info: {file_info}")
        logger.debug(f"System: {system}")
        # Don't raise an exception, try to continue with the file as-is
        logger.warning("Skipping extraction, will try to use the file as-is")
        return False


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
