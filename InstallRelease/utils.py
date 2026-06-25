"""
Re-usable utilities independent of the application logic.
"""

import bz2
import dataclasses
import gzip
import json
import logging
import os
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError
from importlib.metadata import (
    version as pkg_version,
)  # renamed to avoid shadow in PackageVersion
from pathlib import Path

import requests
import zstandard as zstd
from rich import print as pprint
from rich.console import Console
from rich.logging import RichHandler
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)
from rich.table import Table
from rich.text import Text

try:
    from magic.compat import detect_from_filename
except ImportError:
    pprint(
        "[red]Failed to find libmagic. Check your installation\n"
        "Refer: https://github.com/ahupp/python-magic#installation [/]"
    )
    sys.exit(1)

requests_session = requests.Session()
console = Console()

REQUEST_TIMEOUT = (10, 60)
DOWNLOAD_CHUNK_SIZE = 1024 * 1024
DOWNLOAD_MAX_RETRIES = 5

# PEP 8: module-level constants are UPPER_CASE
_COLORS = {
    "green": "#8CC265",
    "light_green": "#D0FF5E bold",
    "blue": "#4AA5F0",
    "cyan": "#76F6FF",
    "yellow": "#F0A45D bold",
    "red": "#E8678A",
    "purple": "#8782E9 bold",
}
_DIM_COLORS = {
    "title": "#B0B0B0",
    "table": "#6F6F6F",
    "border": "#565656",
    "columns": ("#B0B0B0", "#9A9A9A", "#848484", "#9A9A9A", "#B0B0B0"),
}

# Direct setup; guard prevents duplicate handlers on module reload
logger = logging.getLogger(__name__)
if not logger.handlers:
    logger.setLevel(logging.DEBUG if os.environ.get("LOG_LEVEL") else logging.INFO)
    logger.addHandler(RichHandler(log_time_format=""))


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

    def local_version(self) -> str | None:
        try:
            return pkg_version(self.package_name)
        except PackageNotFoundError:
            return None

    def latest_version(self) -> str | None:
        if self._latest_version is not None:
            return self._latest_version
        try:
            data = requests_session.get(self.url, timeout=REQUEST_TIMEOUT).json()
            self._latest_version = data["info"]["version"]
            return self._latest_version
        except requests.RequestException:
            logger.warning(f"Failed to fetch version for {self.package_name}")
            return None


def filter_dataclass(data: dict, obj):
    """Filter a dict to only fields present in the dataclass, then instantiate it."""
    fields = {f.name for f in dataclasses.fields(obj)}
    return obj(**{k: v for k, v in data.items() if k in fields})


FilterDataclass = filter_dataclass  # backward-compat alias


def is_none(val) -> bool:
    """True for None, empty str/dict/list, or any non-collection type."""
    return not isinstance(val, (str, dict, list)) or not val


@dataclass
class ShellOutputs:
    stdout: list[str]
    stderr: list[str]
    returncode: int


@dataclass(frozen=True)
class TableTheme:
    title_style: str = _COLORS["light_green"]
    table_style: str = _COLORS["purple"]
    border_style: str = ""
    column_styles: tuple[str, ...] = (
        _COLORS["yellow"],
        _COLORS["red"],
        _COLORS["green"],
        _COLORS["cyan"],
        _COLORS["blue"],
    )


DIM_TABLE_THEME = TableTheme(
    title_style=_DIM_COLORS["title"],
    table_style=_DIM_COLORS["table"],
    border_style=_DIM_COLORS["border"],
    column_styles=_DIM_COLORS["columns"],
)
DEFAULT_TABLE_THEME = TableTheme()


def sh(command: str, interactive: bool = False) -> ShellOutputs:
    """Run a shell command and return its output."""
    try:
        if interactive:
            proc = subprocess.Popen(command, shell=True)
            proc.wait()
            return ShellOutputs([], [], proc.returncode)

        proc = subprocess.run(command, shell=True, capture_output=True)
        enc = sys.__stdout__.encoding or "utf-8"
        def decode(b):
            return [
                    line for line in b.decode(enc, "ignore").split("\n") if line
                ]
        stdout = decode(proc.stdout)
        logger.debug(f"stdout for {command}:\n{stdout}")
        return ShellOutputs(stdout, decode(proc.stderr), proc.returncode)
    except Exception as e:
        logger.error(f"Exception for {command}: {e}")
        return ShellOutputs([], [], 1)


def mkdir(path: str):
    Path(path).expanduser().mkdir(parents=True, exist_ok=True)


def download(url: str, at: str) -> str:
    """Download a file with retry/resume support via HTTP Range headers."""
    file_name = url.split("/")[-1]
    output_path = os.path.join(at, file_name)
    os.makedirs(at, exist_ok=True)

    progress_columns = [
        SpinnerColumn(),
        TextColumn("{task.description}"),
        BarColumn(),
        DownloadColumn(),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
    ]

    with (
        open(output_path, "wb+") as fw,
        Progress(*progress_columns, console=console, transient=True) as progress,
    ):
        task_id = None
        for attempt in range(1, DOWNLOAD_MAX_RETRIES + 1):
            resume_at = fw.tell()
            try:
                with requests_session.get(
                    url,
                    stream=True,
                    timeout=REQUEST_TIMEOUT,
                    headers={"Range": f"bytes={resume_at}-"} if resume_at else {},
                ) as resp:
                    resp.raise_for_status()
                    if resume_at and resp.status_code != 206:
                        fw.seek(0)
                        fw.truncate()
                        resume_at = 0

                    if task_id is None:
                        total = int(resp.headers.get("content-length") or 0) + resume_at
                        task_id = progress.add_task(
                            f"Downloading {file_name}", total=total or None
                        )
                    progress.update(task_id, completed=resume_at)

                    for chunk in resp.iter_content(chunk_size=DOWNLOAD_CHUNK_SIZE):
                        if chunk:
                            fw.write(chunk)
                            progress.update(task_id, advance=len(chunk))
                break
            except (
                requests.exceptions.ConnectionError,
                requests.exceptions.ChunkedEncodingError,
                requests.exceptions.Timeout,
            ) as e:
                # ponytail: bounded retry + Range resume. Ceiling: assumes the
                # server honours Range (we restart on a 200) and serves raw bytes
                # (no transfer Content-Encoding, true for GitHub/GitLab release
                # assets) so offsets match what we wrote. Upgrade: verify a checksum.
                if attempt == DOWNLOAD_MAX_RETRIES:
                    raise
                fw.flush()
                logger.warning(
                    f"Download interrupted ({e.__class__.__name__}); "
                    f"resuming from {fw.tell()} bytes (attempt {attempt}/{DOWNLOAD_MAX_RETRIES - 1})"
                )
                time.sleep(2 ** (attempt - 1))

    logger.info(f"Downloaded: '{file_name}' at {at}")
    return output_path


def extract(path: str, at: str) -> bool:
    """Extract compressed/archived files including .pkg.tar.zst."""
    try:
        mime = detect_from_filename(path).mime_type
        logger.debug(f"Extracting {path!r} (mime: {mime})")

        if mime == "application/javascript":
            return True

        if mime == "application/x-7z-compressed":
            if platform.system().lower() == "linux":
                sh(f"7z x {path} -o{at}")

        elif mime == "application/x-bzip2" or path.endswith((".bz2", ".tbz")):
            if path.endswith(".tar.bz2") or path.endswith(".tbz"):
                with tarfile.open(path, "r:bz2") as tar:
                    tar.extractall(path=at)
            else:
                with (
                    bz2.open(path, "rb") as f_in,
                    open(Path(at) / Path(path).stem, "wb") as f_out,
                ):
                    shutil.copyfileobj(f_in, f_out)

        elif path.endswith(".gz") and not path.endswith((".tar.gz", ".tgz")):
            with (
                gzip.open(path, "rb") as f_in,
                open(Path(at) / Path(path).stem, "wb") as f_out,
            ):
                shutil.copyfileobj(f_in, f_out)

        elif path.endswith((".pkg.tar.zst", ".tar.zst")):
            with (
                open(path, "rb") as f,
                zstd.ZstdDecompressor().stream_reader(f) as reader,
            ):
                with tarfile.open(fileobj=reader, mode="r|") as tar:
                    tar.extractall(path=at)

        else:
            shutil.unpack_archive(path, at)

        return True
    except Exception as e:
        logger.error(f"Can't extract {path!r}: {e}")
        raise Exception("Invalid file") from e


def listItemsMatcher(patterns: list[str], word: str) -> float:
    if not patterns:
        return 0.0
    return sum(1 for p in patterns if re.search(p.lower(), word.lower())) / len(
        patterns
    )


def threads(funct, data, max_workers: int = 5, return_result: bool = True) -> list:
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = list(executor.map(funct, data))
    return results if return_result else []


def show_table(
    data: list[dict],
    ignore_keys: list | None = None,
    title: str = "",
    border_style: str = "",
    no_wrap: bool = True,
    theme: TableTheme | None = None,
):
    """Render a rich table from a list of dicts."""
    ignore_keys = ignore_keys or []
    theme = theme or DEFAULT_TABLE_THEME

    table = Table(
        title=Text(title, style=theme.title_style),
        style=theme.table_style,
        border_style=border_style or theme.border_style,
    )
    keys = [k for k in (data[0] if data else {}) if k not in ignore_keys]
    for i, col in enumerate(keys):
        table.add_column(
            col,
            justify="left",
            style=theme.column_styles[i % len(theme.column_styles)],
            no_wrap=no_wrap,
        )
    for row in data:
        table.add_row(*[str(row.get(k, "")) for k in keys])

    print()
    Console().print(table)


def to_words(text: str, ignore_words: list[str] | None = None) -> list[str]:
    ignore_words = ignore_words or []
    return [
        w
        for part in text.lower().replace("_", "-").split("-")
        if (w := re.sub(r"\d", "", part)) and w not in ignore_words
    ]
