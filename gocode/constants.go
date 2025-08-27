package main

import (
	"os"
	"path/filepath"
	"runtime"
)

var (
	HOME = func() string {
		home := os.Getenv("HOME")
		if home == "" {
			home = os.Getenv("USERPROFILE") // For Windows
		}
		return home
	}()

	BinAt    = "bin"
	DirName  = "install_release"
	StateAt  = filepath.Join(DirName, "state.json")
	ConfigAt = filepath.Join(DirName, "config.json")
)

// Colors for terminal output
var Colors = map[string]string{
	"green":       "#8CC265",
	"light_green": "#D0FF5E bold",
	"blue":        "#4AA5F0",
	"cyan":        "#76F6FF",
	"yellow":      "#F0A45D bold",
	"red":         "#E8678A",
	"purple":      "#8782E9 bold",
}

// Platform paths mapping - matches Python version structure
var StatePaths = map[string]string{
	"linux":  filepath.Join(HOME, ".config", StateAt),
	"darwin": filepath.Join(HOME, "Library", ".config", StateAt),
}

var ConfigPaths = map[string]string{
	"linux":  filepath.Join(HOME, ".config", ConfigAt),
	"darwin": filepath.Join(HOME, "Library", ".config", ConfigAt),
}

var BinPaths = map[string]string{
	"linux":  filepath.Join(HOME, BinAt),
	"darwin": filepath.Join(HOME, BinAt),
}

// PlatformPath provides path based on platform - matches Python version logic
func PlatformPath(paths map[string]string, alt string) string {
	system := getSystem()

	if alt != "" && alt != "null" {
		return alt
	}

	if path, exists := paths[system]; exists {
		// Check and create directory if needed
		dirPath := filepath.Dir(path)
		if dirPath != "" {
			if err := os.MkdirAll(dirPath, 0755); err != nil {
				// Log error but don't exit - let the calling code handle it
				return path
			}
		}
		return path
	} else {
		// Return a default path instead of exiting
		return filepath.Join(HOME, ".config", StateAt)
	}
}

// StatePath returns the state file path for the current platform
func StatePath() string {
	return PlatformPath(StatePaths, "")
}

// ConfigPath returns the config file path for the current platform
func ConfigPath() string {
	return PlatformPath(ConfigPaths, "")
}

// BinPath returns the binary installation path for the current platform
func BinPath() string {
	return PlatformPath(BinPaths, "")
}

// getSystem returns the current operating system
func getSystem() string {
	// Use runtime.GOOS instead of env var for more reliable detection
	return runtime.GOOS
}
