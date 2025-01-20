#!/bin/bash
# set -x

# Example Usage via curl:
# 1. curl -sL https://raw.githubusercontent.com/Rishang/install-release/main/ir.sh | bash -s -- --repo tomnomnom/gron --release 1.0.0 --name gron --binary-path /usr/local/bin --binary-name gron
# 2. curl -sL https://raw.githubusercontent.com/Rishang/install-release/main/ir.sh | bash -s -- --release-file-url https://github.com/Rishang/install-release/releases/download/v4.5/install-release-Linux-amd64 --binary-path ./ --binary-name test

# Function to print usage
print_usage() {
  echo "Install a release from a GitHub repository"
  echo "Requirements: curl, jq, file, tar, unzip"
  echo ""
  echo "Options:"
  echo "  --repo REPO        GitHub repository (e.g. tomnomnom/gron)"
  echo "  --release RELEASE  Release version (e.g. 1.0.0)"
  echo "  --name NAME        Binary name (default to repo name)"
  echo "  --release-file-url URL  Release file URL (e.g. https://github.com/Rishang/install-release/releases/download/v0.1.0/install-release-linux-amd64)"
  echo "  --binary-path PATH  Binary path (e.g. /usr/local/bin)"
  echo "  --binary-name NAME  Binary name (e.g. gron)"
  echo "Usage: $0 --repo REPO --release RELEASE [--name NAME] [--release-file-url URL] [--binary-path PATH] [--binary-name NAME]"
  echo "Example: $0 --repo tomnomnom/gron --release 1.0.0 [--name gron] [--binary-path /usr/local/bin] [--binary-name gron]"
  exit 1
}

# Function to parse arguments
parse_arguments() {
  while [ "$1" != "" ]; do
    case $1 in
      --repo ) shift
        repo=$1
        ;;
      --release ) shift
        release=$1
        ;;
      --release-file-url ) shift
        release_file_url=$1
        ;;
      --binary-path ) shift
        binary_path=$1
        ;;
      --binary-name ) shift
        binary_name=$1
        ;;
      --name ) shift
        name=$1
        ;;
      * ) print_usage
        exit 1
    esac
    shift
  done

  # Check if all required arguments are provided
  if [ -z "$repo" ] || [ -z "$release" ] && [ -z "$release_file_url" ]; then
    print_usage
  fi

  # Default to repo name if name is not provided
  if [ -z "$name" ]; then
    if [ -n "$repo" ]; then
      name=$(basename $repo)
    else
      name=$binary_name  # Provide a default name if repo is not set
    fi
  fi

  # Default binary path if not provided
  if [ -z "$binary_path" ]; then
    binary_path="/usr/local/bin"
  fi

  # Default binary name if not provided
  if [ -z "$binary_name" ]; then
    binary_name=$name
  fi

  # Automatically detect platform and architecture
  platform=$(uname | tr '[:upper:]' '[:lower:]')
  arch=$(uname -m)

  # Normalize architecture names
  case "$arch" in
    x86_64) arch="amd64" ;;
    aarch64) arch="arm64" ;;
    armv7l) arch="armv7" ;;
  esac
}

# Function to query GitHub API for the specific release
query_github_api() {
  # Remove 'https://github.com/' from repo if present
  repo=$(echo $repo | sed 's|https://github.com/||')
  release_info=$(curl -s https://api.github.com/repos/$repo/releases/tags/$release)

  # Extract the download URL for the desired platform and architecture
  url=$(echo $release_info | jq -r ".assets[] | select(.name | test(\"$platform.*$arch\")) | .browser_download_url")

  if [ -z "$url" ]; then
    echo "No suitable release found for $platform and $arch"
    exit 1
  fi

  echo $url
}

# Function to download and extract release
download_and_extract() {
  local url=$1
  # echo $url
  echo "Downloading $url"
  file_name=$(basename $url)
  tmp_dir=$(mktemp -d -t ${name}_${platform}_${arch}_XXXXXXXXXX)
  curl -L $url -o $tmp_dir/$file_name
  # check if the file is a tarball or a zip file

  if [[ $file_name == *.zip ]]; then
    unzip $tmp_dir/$file_name -d $tmp_dir
    rm $tmp_dir/$file_name
  elif [[ $file_name == *.tar* || $file_name == *.tgz ]]; then
    tar -xzvf $tmp_dir/$file_name -C $tmp_dir
    rm $tmp_dir/$file_name
  # check if file is binary executable via file command
  elif [[ $(file $tmp_dir/$file_name | grep -i "executable") ]]; then
    echo "File is binary executable"
  else
    # check if file is binary executable via file command
    echo "Unknown file format"
    file $tmp_dir/$file_name
  fi

}

# Function to find the executable binary
find_executable() {
  binary=$(find $tmp_dir -type f)
  echo $binary
  
  if [ -z "$binary" ]; then
    echo "No executable binary found for $name"
    cleanup
    exit 1
  fi
}

# Function to install the binary
install_binary() {
  local binary_path=$1
  local binary_name=$2
  # Create binary path directory if it doesn't exist
  mkdir -p $binary_path
  install $binary $binary_path/$binary_name
}

# Function to clean up temporary directory
cleanup() {
  rm -rf $tmp_dir
}

# Function to test the installation
test_installation() {
  if [ -x "$binary_path/$binary_name" ]; then
    echo "${binary_name} installed successfully at $binary_path/$binary_name"
    $binary_path/$binary_name --version
  else
    echo "Failed to install ${binary_name} at $binary_path/$binary_name"
    exit 1
  fi
}

# Main function
main() {
  parse_arguments "$@"
  if [ -n "$release_file_url" ]; then
    download_and_extract $release_file_url
  else
    url=$(query_github_api)
    download_and_extract $url
  fi
  find_executable
  install_binary $binary_path $binary_name
  cleanup
  test_installation
}

# Run the main function
main "$@"
