package main

import (
	"os"
	"path/filepath"
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

// StatePath returns the state file path for the current platform
func StatePath() string {
	system := getSystem()
	switch system {
	case "linux":
		return filepath.Join(HOME, ".config", StateAt)
	case "darwin":
		return filepath.Join(HOME, "Library", ".config", StateAt)
	default:
		return filepath.Join(HOME, ".config", StateAt)
	}
}

// ConfigPath returns the config file path for the current platform
func ConfigPath() string {
	system := getSystem()
	switch system {
	case "linux":
		return filepath.Join(HOME, ".config", ConfigAt)
	case "darwin":
		return filepath.Join(HOME, "Library", ".config", ConfigAt)
	default:
		return filepath.Join(HOME, ".config", ConfigAt)
	}
}

// BinPath returns the binary installation path for the current platform
func BinPath() string {
	system := getSystem()
	switch system {
	case "linux":
		return filepath.Join(HOME, BinAt)
	case "darwin":
		return filepath.Join(HOME, BinAt)
	default:
		return filepath.Join(HOME, BinAt)
	}
}

// getSystem returns the current operating system
func getSystem() string {
	return os.Getenv("GOOS")
}
