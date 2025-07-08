package main

import (
	"os"

	"github.com/spf13/cobra"
)

var (
	debug   bool
	quiet   bool
	force   bool
	approve bool
)

func main() {
	var rootCmd = &cobra.Command{
		Use:   "ir",
		Short: "GitHub/GitLab Release Installer, based on your system",
		Long:  `Install Release is a CLI tool to install any single-binary executable package for your device(Linux/MacOS/WSL) directly from their GitHub or GitLab releases and keep them updated.`,
	}

	// Global flags
	rootCmd.PersistentFlags().BoolVarP(&debug, "debug", "v", false, "set verbose mode")
	rootCmd.PersistentFlags().BoolVarP(&quiet, "quiet", "q", false, "set quiet mode")
	rootCmd.PersistentFlags().BoolVarP(&force, "force", "F", false, "set force")
	rootCmd.PersistentFlags().BoolVarP(&approve, "approve", "y", false, "skip confirmation (y/n) prompt")

	// Add commands
	rootCmd.AddCommand(getCmd())
	rootCmd.AddCommand(upgradeCmd())
	rootCmd.AddCommand(listCmd())
	rootCmd.AddCommand(removeCmd())
	rootCmd.AddCommand(configCmd())
	rootCmd.AddCommand(stateCmd())
	rootCmd.AddCommand(pullCmd())
	rootCmd.AddCommand(holdCmd())
	rootCmd.AddCommand(meCmd())

	if err := rootCmd.Execute(); err != nil {
		// Error is already printed by Cobra
		os.Exit(1)
	}
}
