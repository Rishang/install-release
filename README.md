<h1 align="center">
  🚀 Install Release 
</h1>

<p align="center">
  <a href="https://shields.io/">
    <img src="https://img.shields.io/badge/Python-3.9_to_3.14-xx.svg" alt="Python Version" />
  </a>
  <a href="https://pepy.tech/project/install-release">
    <img src="https://static.pepy.tech/personalized-badge/install-release?period=total&units=international_system&left_color=black&right_color=orange&left_text=Downloads" alt="Downloads" />
  </a>
<p>

**Install Release** is a CLI tool by name `ir` to install any single-binary executable package for your device(Linux/MacOS/WSL) directly from their GitHub or GitLab releases and keep them updated. Consider it as a small package manager to install single binary tools from GitHub/GitLab releases.

This can be any tool you want to install, which is pre-compiled for your device and present on GitHub or GitLab releases.

> INFO: It's mainly for installing tools that are not directly available officially by package managers like `apt, yum, pacman, brew` etc.

<p align="center">
  <img src=".github/images/flow.png" alt="How it works" width="800">
</p>

<!-- Table of content -->

## Table of Contents 📚

- [Table of Contents 📚](#table-of-contents-)
- [Getting started ⚡](#getting-started-)
    - [Manage your tools 🛠️](#manage-your-tools-)
- [Prerequisites 📋](#prerequisites-)
- [Updating `install-release` 🔄](#updating-install-release-)
- [Example usage `ir --help` 💡](#example-usage-ir---help-)
    - [Install completion for cli 🎠](#install-completion-for-cli-)
    - [Install tool from GitHub/GitLab releases 🌈](#install-tool-from-githubgitlab-releases-)
    - [List installed tools 📋](#list-installed-tools-)
    - [Remove installed release ❌](#remove-installed-release-)
    - [Update all previously installed tools to the latest version 🕶️](#update-all-previously-installed-tools-to-the-latest-version-)
    - [Pull state templates for installing tools 📄](#pull-state-templates-for-installing-tools-)
    - [Hold Update to specific installed tool ✋](#hold-update-to-specific-installed-tool-)
    - [Config tool installation path 🗂️](#config-tool-installation-path-)
    - [Config updates for pre-release versions 🔌](#config-updates-for-pre-release-versions-)
    - [Configure GitHub/GitLab tokens for higher rate limit 🔑](#configure-githubgitlab-tokens-for-higher-rate-limit-)
    - [Configure custom release file 🔦](#configure-custom-release-file-)

## Getting started ⚡

```bash
# Install ir
pip install -U install-release
```

Example: Installing [deno (Rust-based JavaScript runtime)](https://github.com/denoland/deno) directly from its GitHub releases:

```bash
# Usage: ir get [GITHUB-URL or GITLAB-URL]
❯ ir get https://github.com/denoland/deno
```

Verify the installation:

```bash
❯ which deno
~/bin/deno

❯ deno --version
deno 1.46.3 ...
```

Example: Installing [GitLab CLI](https://gitlab.com/gitlab-org/cli) with a custom binary name `glab`

```bash
❯ ir get https://gitlab.com/gitlab-org/cli -n glab
```

Verify the installation:

```bash
❯ which glab
~/bin/glab

❯ glab --version
glab 1.80.0 ...
```

### Manage your tools 🛠️

Once installed, you can manage your tools with these simple commands:

- **List**: `ir ls` — See all installed tools and versions.
- **Update**: `ir upgrade` — Upgrade all installed tools to their latest releases.
- **Remove**: `ir rm deno` — Remove a tool from your system.

For more details, check the [Table of Contents](#table-of-contents-).


## Prerequisites 📋

- python3.8 or higher
- [libmagic](https://github.com/ahupp/python-magic#installation)
- Default installation path: `~/bin/` (Ensure this is in your `PATH`)

```bash
# Add this to your ~/.bashrc or ~/.zshrc
export PATH=$HOME/bin:$PATH
```

## Updating `install-release` 🔄

For seeing version:

```bash
ir me --version
```

For updating:

```bash
ir me --upgrade
```

## Example usage `ir --help` 💡

```
# Help page

❯ ir --help
Usage: ir [OPTIONS] COMMAND [ARGS]...

  GitHub Release Installer, based on your system

  Commands:
    get      | Install GitHub/GitLab release, cli tool
    ls       | list all installed releases, cli tools
    rm       | remove any installed release, cli tools
    upgrade  | Upgrade all installed releases, cli tools
    state    | show currently stored state
    config   | Set configs for tool
    pull     | Install tools from a remote state
    hold     | Keep updates a tool on hold.
    me       | Update ir tool.
```

For sub-command help use: `ir <sub-command> --help`

Example: `ir get --help`

#### Install completion for cli 🎠

```bash
# ir --install-completion [SHELL: bash|zsh|fish|powershell]
# Example for zsh:
ir --install-completion zsh
```

#### Install tool from GitHub/GitLab releases 🌈

```bash
❯ ir get "https://github.com/ahmetb/kubectx"

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
 INFO     install /tmp/dn_kubectx_ph6i7dmk/kubectx /home/noobi/bin/kubectx                                                                  core.py:132
 INFO     Installed: kubectx
```

```
# checking if kubectx is installed
❯ which kubectx
/home/noobi/bin/kubectx

❯ kubectx --version
0.9.4
```

#### List installed tools 📋

```bash
❯ ir ls

                       Installed tools
┏━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Name      ┃ Version ┃ Url                                  ┃
┡━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ terrascan │ v1.15.2 │ https://github.com/tenable/terrascan │
│ gron      │ v0.7.1  │ https://github.com/tomnomnom/gron    │
│ kubectx   │ v0.9.4  │ https://github.com/ahmetb/kubectx    │
└───────────┴─────────┴──────────────────────────────────────┘
```

#### Remove installed release ❌

```bash
# Remove installed release

❯ ir rm gron

INFO     Removed: gron
```

#### Update all previously installed tools to the latest version 🕶️

```bash
❯ ir upgrade

Fetching: https://github.com/tenable/terrascan#terrascan
Fetching: https://github.com/ahmetb/kubectx#kubectx

Following tools will be upgraded:

terrascan

Upgrade these tools, (Y/n): y

Updating: terrascan, v1.15.0 => v1.15.2
 INFO     Downloaded: 'terrascan_1.15.2_Linux_x86_64.tar.gz' at /tmp/dn_terrascan_0as71a6v
 INFO     install /tmp/dn_terrascan_0as71a6v/terrascan ~/bin/terrascan
 INFO     Installed: terrascan

Progress... ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100% 0:00:00
```

#### Pull state templates for installing tools 📄

You can push your state to somewhere like GitHub and use it for any other device, to make a sync for tools installed via ir

```bash
❯ ir pull --url https://raw.githubusercontent.com/Rishang/dotFiles/main/templates/install-release/state.json
```

#### Hold Update to specific installed tool ✋

In case you want to hold an update to the specific tool, you can use `hold {tool-name}` command which will pause update for that tool.

Example: keep tool named [k9s](https://github.com/derailed/k9s) update on hold

```bash
❯ ir hold k9s
 INFO     Update on hold for, k9s to True
```

You can list tools on hold updates by `ls --hold` command

```bash
❯ ir ls --hold
             Installed tools kept on hold
┏━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Name ┃ Version ┃ Url                               ┃
┡━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ k9s  │ v0.26.7 │ https://github.com/derailed/k9s   │
└──────┴─────────┴───────────────────────────────────┘
```

In case you want to unhold update to the specific tool, you can use `hold --unset {tool-name}` command by which it will pause update for that tool.

```
❯ ir hold --unset k9s
 INFO     Update on hold for, k9s to False
```

#### Config tool installation path 🗂️

```bash
❯ ir config --path ~/.local/bin

INFO   updated path to:  ~/.local/bin
INFO   Done
```

#### Config updates for pre-release versions 🔌

This is useful when you want to install pre-release versions of tools like beta or alpha releases. By default, it is set to `False` in which case it will only check for latest release.

```bash
❯ ir config --pre-release
```

#### Configure GitHub/GitLab tokens for higher rate limit 🔑

> For GitHub:
```bash
❯ ir config --token [your github token]

INFO: Updated GitHub token
INFO: Done.
```

> For GitLab:
```bash
❯ ir config --gitlab-token [your gitlab token]

INFO: Updated GitLab token
INFO: Done.
```

#### Configure custom release file 🔦

In rare cases where install-release does not automatically find the correct release file for your system, you can manually specify the release file name from the GitHub or GitLab release page.

- The tool will parse the release file name into keywords (removing version numbers and file extensions), then store these keywords in the state file to match the release file name during future tool upgrades.

> Note: Even though this fixes the issue where `install release` fails to identify correct release package for your system, It will be helpful if you raise Github Issue in this case to make this tool better over the time.

Usage:
```bash
❯ ir get [GITHUB-URL or GITLAB-URL] -r [release file]
```

Example: Installing the bore tool from GitHub with the release file name `bore-v0.4.0-arm-unknown-linux-musleabi.tar.gz`. Here, the keywords generated are: `bore, v0.4.0, arm, linux, musleabi`

```bash
❯ ir get https://github.com/ekzhang/bore -r bore-v0.4.0-arm-unknown-linux-musleabi.tar.gz
```
