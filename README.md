# install-releases

install-releases is a cli tool to install tools based on your device info directly from github releases and keep them updated.


## Prerequisites

- python3.8 or higher

- [libmagic](https://github.com/ahupp/python-magic#installation)
- Default releases Installation Path is: `~/.releases-bin/`,
This is the path where installed tools are stored.

- In order to run installed tools, you need to add the following line your `~/.bashrc` or `~/.zshrc` file:

```bash
export PATH=$HOME/.releases-bin:$PATH
```


## Install any tool

Example usage:

```bash
# Installing gron tool from github from for my system (linux x86_64):
# https://github.com/tomnomnom/gron/releases


python cli.py get "https://github.com/tomnomnom/gron"

  INFO     Downloaded: 'gron-linux-amd64-0.7.1.tgz' at /tmp/dn_gron_eybzs568
  INFO     installed /tmp/dn_gron_eybzs568/gron to /home/noobi/.releases-bin/gron
```


### Help page

```
$ python cli.py --help
Usage: cli.py [OPTIONS] COMMAND [ARGS]...

  release Installer

Commands:
  get      | Install github release, cli tool
  upgrade  | Upgrade all github release, cli tool
```
