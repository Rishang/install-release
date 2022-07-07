# install-releases
[![Python Version](https://img.shields.io/badge/Python-3.8_to_3.10-xx.svg)](https://shields.io/) [![Downloads](https://static.pepy.tech/personalized-badge/install-release?period=month&units=international_system&left_color=black&right_color=orange&left_text=Downloads)](https://pepy.tech/project/install-release)

install-releases is a cli tool to install tools based on your device info directly from github releases and keep them updated.

This can be any tool you want to install, which is pre-compiled for your device and present on github releases.

> Also it's mainly for installing tools that are not available in the official repositories or package managers.

```bash
# Install install-releases
pip install -U install-release
```

```
# Example Installation a tool named `gron` directly from github releases

❯ install-release install https://github.com/tomnomnom/gron 
```

![demo](.github/images/demo.png)


Checking for gron is installed using installed-release:

```
❯ which gron
/home/noobi/.release-bin/gron

❯ gron --help
Transform JSON (from a file, URL, or stdin) into discrete assignments to make it greppable
... # more
```

## Prerequisites

- python3.8 or higher

- [libmagic](https://github.com/ahupp/python-magic#installation)
- Default releases Installation Path is: `~/.release-bin/`,
This is the path where installed tools will get stored.

- In order to run installed tools, you need to add the following line your `~/.bashrc` or `~/.zshrc` file:

```bash
export PATH=$HOME/.release-bin:$PATH
```


## Install this package

```bash
pip install -U install-release
```


### Example usage `install-release`


```
# Help page

❯ install-release --help
Usage: install-release [OPTIONS] COMMAND [ARGS]...

  Github Release Installer, based on your system

  Commands:
    install  | Install github release, cli tool
    ls       | list all installed release, cli tools
    rm       | remove any installed release, cli tools
    upgrade  | Upgrade all installed release, cli tools

```

For sub command help use: `install-release <sub-command> --help`

Example: `install-release get --help`



#### Install tool from github releases

```bash
❯ install-release get "https://github.com/ahmetb/kubectx"

📑 Repo     : ahmetb/kubectx
🌟 Stars    : 13295
✨ Language : Go
🔥 Title    : Faster way to switch between clusters and namespaces in kubectl

                              🚀 Install: kubectx                               
┏━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━┓
┃ Name    ┃ Selected Item                      ┃ Version ┃ Size Mb ┃ Downloads ┃
┡━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━┩
│ kubectx │ kubectx_v0.9.4_linux_x86_64.tar.gz │ v0.9.4  │ 1.0     │ 43811     │
└─────────┴────────────────────────────────────┴─────────┴─────────┴───────────┘
Install this tool (Y/n): y
 INFO     Downloaded: 'kubectx_v0.9.4_linux_x86_64.tar.gz' at /tmp/dn_kubectx_ph6i7dmk                                                               utils.py:159
 INFO     install /tmp/dn_kubectx_ph6i7dmk/kubectx /home/noobi/.release-bin/kubectx                                                                  core.py:132
 INFO     Installed: kubectx
```
```
# checking if kubectx is installed
❯ which kubectx
/home/noobi/.release-bin/kubectx

❯ kubectx --version
0.9.4
```

#### List installed tools

```bash
❯ install-release ls

                       Installed tools                        
┏━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Name      ┃ Version ┃ Url                                  ┃
┡━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ terrascan │ v1.15.2 │ https://github.com/tenable/terrascan │
│ gron      │ v0.7.1  │ https://github.com/tomnomnom/gron    │
└───────────┴─────────┴──────────────────────────────────────┘    
```

#### Remove installed release

```bash
# Remove installed release

❯ install-release rm gron
    
INFO     Removed: gron           
```

#### Update all previously installed tools to the latest version

```bash
❯ install-release upgrade

Fetching: https://github.com/tenable/terrascan
Updating: terrascan, v1.15.0 => v1.15.2
 INFO     Downloaded: 'terrascan_1.15.2_Linux_x86_64.tar.gz' at /tmp/dn_terrascan_0as71a6v
 INFO     install /tmp/dn_terrascan_0as71a6v/terrascan /home/noobi/.release-bin/terrascan
 INFO     Installed: terrascan

Fetching: https://github.com/tomnomnom/gron
 INFO     No updates

Progress... ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% 0:00:00 
```

