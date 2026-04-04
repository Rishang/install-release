"""
All the re-usable utilities independent of the application logic for the project are here
"""

import os
import re
import sys
import json
import bz2
import tarfile
import gzip
import shutil
import logging
import platform
import subprocess
import dataclasses
from pathlib import Path
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
from importlib.metadata import version, PackageNotFoundError

import requests
import zstandard as zstd
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

requests_session = requests.Session()

console = Console()

_colors = {
    "green": "#8CC265",
    "light_green": "#D0FF5E bold",
    "blue": "#4AA5F0",
    "cyan": "#76F6FF",
    "yellow": "#F0A45D bold",
    "red": "#E8678A",
    "purple": "#8782E9 bold",
}


def _logger(flag: str = ""):
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG if os.environ.get(flag) else logging.INFO)
    logger.addHandler(RichHandler(log_time_format=""))
    return logger


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
    stdout: list[str]
    stderr: list[str]
    returncode: int


def sh(command: str, interactive: bool = False) -> ShellOutputs:
    """Run a shell command and return its output."""
    try:
        if interactive:
            process = subprocess.Popen(command, shell=True)
            process.wait()
            return ShellOutputs(stdout=[], stderr=[], returncode=process.returncode)

        process = subprocess.Popen(
            command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        raw_out, raw_err = process.communicate()

        encoding = sys.__stdout__.encoding or "utf-8"
        stdout = list(filter(None, raw_out.decode(encoding, "ignore").split("\n")))
        stderr = list(filter(None, raw_err.decode(encoding, "ignore").split("\n")))

        logger.debug(f"stdout for {command}:\n{stdout}")
        return ShellOutputs(stdout=stdout, stderr=stderr, returncode=process.returncode)
    except Exception as e:
        logger.error(f"Exception for {command}: {e}")
        return ShellOutputs(stdout=[], stderr=[], returncode=1)


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
    """Extract tar/archived files, including .pkg.tar.zst"""

    try:
        system = platform.system().lower()
        file_info = detect_from_filename(path)
        logger.debug(file_info)
        if file_info.mime_type == "application/javascript":
            return True

        if file_info.mime_type == "application/x-7z-compressed":
            if system in ["linux"]:
                cmd = f"7z x {path} -o{at}"
                logger.debug("command: " + cmd)
                sh(cmd)
            elif system == "windows":
                # 'C:\\Program Files\\7-zip\\7z.exe'
                pass
        elif file_info.mime_type == "application/x-bzip2" or path.endswith(
            (".bz2", ".tbz")
        ):
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

        elif path.endswith(".gz") and not path.endswith((".tar.gz", ".tgz")):
            # Single file compressed with gzip
            logger.debug(f"Extracting gzip file: {path}")
            # Single file compressed with gzip
            with gzip.open(path, "rb") as f_in:
                # Remove .gz extension for output filename
                output_file = os.path.join(at, os.path.basename(path)[:-3])
                with open(output_file, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)
                logger.debug(f"Extracted to: {output_file}")

        elif path.endswith((".pkg.tar.zst", ".tar.zst")):
            logger.debug(f"Extracting zstd tar file: {path}")
            dctx = zstd.ZstdDecompressor()
            with open(path, "rb") as compressed:
                with dctx.stream_reader(compressed) as reader:
                    # Wrap the stream in tarfile
                    with tarfile.open(fileobj=reader, mode="r|") as tar:
                        tar.extractall(path=at)
            logger.debug(f"Extracted to: {at}")

        else:
            shutil.unpack_archive(path, at)

        return True
    except Exception as e:
        logger.error(f"can't extract: {path}, error: {e}")
        raise Exception("Invalid file")


def listItemsMatcher(patterns: list[str], word: str) -> float:
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
    data: list[dict], ignore_keys: list = [], title: str = "", border_style=""
):
    """rich table"""

    def dict_list_tbl(items=list[dict], ignore_keys: list = []):
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


def to_words(text: str, ignore_words: list[str] = []) -> list[str]:
    text = text.lower().replace("_", "-").split("-")
    words = []
    for w in text:
        if w not in ignore_words:
            w = re.sub(r"\d", "", w)
            if w != "":
                words.append(w)
    return words
