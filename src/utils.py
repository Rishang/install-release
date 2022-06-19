import os
import re
import sys
import json
import shutil
import logging
import platform
import subprocess
import dataclasses
from typing import List
from dataclasses import dataclass

# pipi
import requests
from rich import print as rprint
from rich.console import Console
from rich.logging import RichHandler
from magic.compat import detect_from_filename

# logging.basicConfig(level=logging.INFO)


# locals
console = Console()


def _logger(flag: str = "", format: str = ""):
    if format == "" or format == None:
        format = "%(levelname)s|%(name)s| %(message)s"

    # message
    logger = logging.getLogger(__name__)

    if os.environ.get(flag) != None:
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
# export loglevel=true
logger = _logger("loglevel")


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
            process = subprocess.Popen(cmd, **self.popen_args)
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
    if not os.path.isdir(path):
        os.makedirs(name=path)
    else:
        ...


def download(url: str, at: str):
    """Download a file"""

    file = requests.get(url, stream=True)
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
        else:
            shutil.unpack_archive(path, at)

        return True
    except:
        logger.error(f"can't extract: {path}")
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


def platform_words() -> list:

    aliases = {
        "x86_64": ["x86", "x64", "amd64", "amd", "x86_64"],
        "aarch64": ["arm64", "aarch64"],
    }

    platform_words = []

    platform_words += [platform.system().lower(), platform.architecture()[0]]

    for alias in aliases:
        if platform.machine().lower() in aliases[alias]:
            platform_words += aliases[alias]

    return platform_words


class EnhancedJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if dataclasses.is_dataclass(o):
            return dataclasses.asdict(o)
        return super().default(o)
