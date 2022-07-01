# install-releases

install-releases is a cli tool to install tools based on your device info directly from github releases and keep them updated.

![demo](.github/images/demo.png)


```
# Checking for gron is installed using installed-release:

❯ which gron
/home/noobi/.releases-bin/gron

❯ gron --help
Transform JSON (from a file, URL, or stdin) into discrete assignments to make it greppable
... # more

```

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

### Example usage:

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

```
# Remove installed release

❯ install-release rm gron
    
INFO     Removed: gron           
```

#### Update all previously installed tools to the latest version

```
❯ install-release upgrade

Fetching: https://github.com/tenable/terrascan
Updating: terrascan, v1.15.0 => v1.15.2
 INFO     Downloaded: 'terrascan_1.15.2_Linux_x86_64.tar.gz' at /tmp/dn_terrascan_0as71a6v
 INFO     install /tmp/dn_terrascan_0as71a6v/terrascan /home/noobi/.releases-bin/terrascan
 INFO     Installed: terrascan

Fetching: https://github.com/tomnomnom/gron
 INFO     No updates

Progress... ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% 0:00:00 
```

### Help page

```
❯ install-release --help
Usage: install-release [OPTIONS] COMMAND [ARGS]...

  Github Release Installer, based on your system

  Commands:
    get      | Install github release, cli tool
    ls       | list all installed release, cli tools
    rm       | remove any installed release, cli tools
    upgrade  | Upgrade all installed release, cli tools
```
