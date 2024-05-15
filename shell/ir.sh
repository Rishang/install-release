#!/bin/bash
# set -x
# Function to print usage
print_usage() {
  echo "Install a release from a GitHub repository"
  echo "Requirements: curl, jq, file, tar, unzip"
  echo ""
  echo "Options:"
  echo "  --repo REPO        GitHub repository (e.g. tomnomnom/gron)"
  echo "  --release RELEASE  Release version (e.g. 1.0.0)"
  echo "  --name NAME        Binary name (default to repo name)"
  echo ""
  echo "Usage: $0 --repo REPO --release RELEASE [--name NAME]"
  echo "Example: $0 --repo tomnomnom/gron --release 1.0.0 [--name gron]"
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
      --name ) shift
               name=$1
               ;;
      * ) print_usage
          exit 1
    esac
    shift
  done

  # Check if all required arguments are provided
  if [ -z "$repo" ] || [ -z "$release" ]; then
    print_usage
  fi

  # Default to repo name if name is not provided
  if [ -z "$name" ]; then
    name=$(basename $repo)
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
  install $binary /usr/local/bin/$name
}

# Function to clean up temporary directory
cleanup() {
  rm -rf $tmp_dir
}

# Function to test the installation
test_installation() {
  if command -v ${name} &> /dev/null; then
    echo "${name} installed successfully in /usr/local/bin"
    ${name} --version
  else
    echo "Failed to install ${name}"
    exit 1
  fi
}

# Main function
main() {
  parse_arguments "$@"
  url=$(query_github_api)
  download_and_extract $url
  find_executable
  install_binary
  cleanup
  test_installation
}

# Run the main function
main "$@"
