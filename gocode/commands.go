package main

import (
	"bufio"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"sync"

	"github.com/charmbracelet/lipgloss"
	"github.com/spf13/cobra"
)

// getCmd represents the get command
func getCmd() *cobra.Command {
	var tagName string
	var name string
	var approve bool

	cmd := &cobra.Command{
		Use:          "get [URL]",
		Short:        "Install GitHub/GitLab release, cli tool",
		Long:         `Install a tool from GitHub or GitLab releases`,
		Args:         cobra.ExactArgs(1),
		SilenceUsage: true,
		RunE: func(cmd *cobra.Command, args []string) error {
			url := args[0]

			// Load configuration
			config := NewConfigManager()
			if err := config.Load(); err != nil {
				return fmt.Errorf("error loading config: %v", err)
			}
			// Debug print of config token removed for security

			// Get repository info
			repo, err := GetRepoInfo(url, config.GetToken(), config.GetGitlabToken())
			if err != nil {
				return fmt.Errorf("error getting repository info: %v", err)
			}

			// Get repository information
			repoInfo, err := repo.Repository()
			if err != nil {
				return fmt.Errorf("error getting repository: %v", err)
			}

			// Get releases
			releases, err := repo.Release(tagName, config.GetPreRelease())
			if err != nil {
				return fmt.Errorf("error getting releases: %v", err)
			}

			if len(releases) == 0 {
				return fmt.Errorf("no releases found")
			}

			// Find the best asset
			asset, err := GetRelease(releases, url, nil)
			if err != nil {
				return fmt.Errorf("error finding release: %v", err)
			}

			// Determine tool name - use repo name if no name provided
			var toolName string
			if name != "" {
				toolName = name
			} else {
				// Extract repository name from URL
				// URL format: https://github.com/owner/repo
				parts := strings.Split(strings.TrimSuffix(url, "/"), "/")
				if len(parts) >= 2 {
					toolName = parts[len(parts)-1] // Get the repo name (last part)
				} else {
					toolName = "unknown"
				}
			}

			// Show information
			fmt.Printf("\n📑 Repo     : %s\n", repoInfo.FullName)
			fmt.Printf("🌟 Stars    : %d\n", repoInfo.StargazersCount)
			fmt.Printf("✨ Language : %s\n", repoInfo.Language)
			fmt.Printf("🔥 Title    : %s\n", repoInfo.Description)

			// Display installation title in bold green
			installTitle := fmt.Sprintf("                              🚀 Install: %s", toolName)
			installStyle := lipgloss.NewStyle().
				Foreground(lipgloss.Color("10")).
				Bold(true)
			fmt.Printf("\n%s\n", installStyle.Render(installTitle))

			// Prepare asset table data
			assetRows := []map[string]string{
				{
					"Name":          toolName,
					"Selected Item": asset.Name,
					"Version":       releases[0].TagName,
					"Size Mb":       fmt.Sprintf("%.1f", asset.SizeMB()),
					"Downloads":     fmt.Sprintf("%d", asset.DownloadCount),
				},
			}
			assetHeaders := []string{"Name", "Selected Item", "Version", "Size Mb", "Downloads"}
			assetColorFuncs := []func(string) string{
				func(s string) string { return lipgloss.NewStyle().Foreground(lipgloss.Color("11")).Render(s) }, // Light Yellow
				func(s string) string { return lipgloss.NewStyle().Foreground(lipgloss.Color("14")).Render(s) }, // Cyan
				func(s string) string { return lipgloss.NewStyle().Foreground(lipgloss.Color("13")).Render(s) }, // Light Magenta
				func(s string) string { return lipgloss.NewStyle().Foreground(lipgloss.Color("10")).Render(s) }, // Light Green
				func(s string) string { return lipgloss.NewStyle().Foreground(lipgloss.Color("12")).Render(s) }, // Light Blue
			}
			PrintTable(assetRows, assetHeaders, assetColorFuncs)

			// Ask for confirmation
			if !approve {
				fmt.Print("Install this tool (Y/n): ")
				reader := bufio.NewReader(os.Stdin)
				response, err := reader.ReadString('\n')
				if err != nil {
					return fmt.Errorf("error reading input: %v", err)
				}

				response = strings.TrimSpace(strings.ToLower(response))
				if response != "" && response != "y" && response != "yes" {
					fmt.Println("Installation cancelled")
					return nil
				}
			}

			// Create temporary directory for extraction
			tempDir := filepath.Join(GetTempDir(), "install-release", "extract")
			if err := Mkdir(tempDir); err != nil {
				return fmt.Errorf("error creating temp directory: %v", err)
			}
			defer RemoveDir(tempDir)

			// Extract the release
			if err := ExtractRelease(asset, tempDir); err != nil {
				return fmt.Errorf("error extracting release: %v", err)
			}

			// Find the executable
			executable, err := FindExecutable(tempDir)
			if err != nil {
				return fmt.Errorf("error finding executable: %v", err)
			}

			// Install the executable
			installPath := config.GetPath()
			var destName string
			if name != "" {
				destName = name
			} else {
				destName = toolName // Use the extracted repo name instead of executable filename
			}

			destPath := filepath.Join(installPath, destName)
			if err := InstallBin(executable, destPath, false, destName); err != nil {
				return fmt.Errorf("error installing binary: %v", err)
			}

			// Save to state - matches Python pattern: cache[key] = release
			// Only store the selected asset (like Python version)
			releases[0].Assets = []ReleaseAssets{*asset}
			state := NewStateManager()
			state.SetByName(url, destName, releases[0])

			return nil
		},
	}

	cmd.Flags().StringVarP(&tagName, "tag", "t", "", "get a specific tag version")
	cmd.Flags().StringVarP(&name, "name", "n", "", "tool name you want")
	cmd.Flags().BoolVarP(&approve, "approve", "y", false, "Approve without Prompt")

	return cmd
}

// upgradeCmd represents the upgrade command
func upgradeCmd() *cobra.Command {
	var force bool
	var skipPrompt bool

	cmd := &cobra.Command{
		Use:          "upgrade",
		Short:        "Upgrade all installed releases, cli tools",
		Long:         `Upgrade all previously installed tools to the latest version`,
		SilenceUsage: true,
		RunE: func(cmd *cobra.Command, args []string) error {
			// Load state
			state := NewStateManager()
			if err := state.Load(); err != nil {
				return fmt.Errorf("error loading state: %v", err)
			}

			// Load configuration
			config := NewConfigManager()
			if err := config.Load(); err != nil {
				return fmt.Errorf("error loading config: %v", err)
			}

			items := state.Items()
			if len(items) == 0 {
				PrintInfo("No installed tools found")
				return nil
			}

			// Track upgrades available
			type UpgradeInfo struct {
				name           string
				currentVersion string
				newVersion     string
				release        *Release
				asset          *ReleaseAssets
				repoURL        string
				key            string
			}

			var availableUpgrades []UpgradeInfo

			// Check all tools for updates with concurrency control (max 5 concurrent)
			const maxConcurrent = 5
			semaphore := make(chan struct{}, maxConcurrent)
			var wg sync.WaitGroup
			var mu sync.Mutex

			for key, release := range items {
				// Extract tool name from key
				var toolName string
				if strings.Contains(key, "#") {
					parts := strings.Split(key, "#")
					toolName = parts[len(parts)-1]
				} else {
					toolName = key
				}

				if release.HoldUpdate {
					continue
				}

				wg.Add(1)
				go func(key string, release *Release, toolName string) {
					defer wg.Done()

					// Acquire semaphore
					semaphore <- struct{}{}
					defer func() { <-semaphore }()

					fmt.Printf("Fetching: %s\n", lipgloss.NewStyle().Foreground(lipgloss.Color("12")).Render(key))

					// Get repository info
					repo, err := GetRepoInfo(release.URL, config.GetToken(), config.GetGitlabToken())
					if err != nil {
						return
					}

					// Get latest release
					releases, err := repo.Release("", config.GetPreRelease())
					if err != nil {
						return
					}

					if len(releases) == 0 {
						return
					}

					latestRelease := releases[0]

					// Check if update is available (compare versions or force)
					if latestRelease.TagName != release.TagName || force {
						// Find the best asset
						asset, err := GetRelease(releases, release.URL, nil)
						if err != nil {
							return
						}

						// Thread-safe append to availableUpgrades
						mu.Lock()
						availableUpgrades = append(availableUpgrades, UpgradeInfo{
							name:           toolName,
							currentVersion: release.TagName,
							newVersion:     latestRelease.TagName,
							release:        latestRelease,
							asset:          asset,
							repoURL:        release.URL,
							key:            key,
						})
						mu.Unlock()
					}
				}(key, release, toolName)
			}

			// Wait for all goroutines to complete
			wg.Wait()

			// Show available upgrades and ask for confirmation (like Python version)
			if len(availableUpgrades) > 0 {
				fmt.Printf("\nFollowing tool will get upgraded.\n\n")

				// Show tool names in one line like Python version
				toolNames := make([]string, len(availableUpgrades))
				for i, upgrade := range availableUpgrades {
					toolNames[i] = upgrade.name
				}
				toolNamesStr := strings.Join(toolNames, " ")
				fmt.Printf("%s\n", lipgloss.NewStyle().Foreground(lipgloss.Color("208")).Bold(true).Render(toolNamesStr))

				if !skipPrompt {
					prompt := lipgloss.NewStyle().Foreground(lipgloss.Color("117")).Bold(true).Render("Upgrade these tools, (Y/n): ")
					fmt.Printf("\n%s", prompt)
					reader := bufio.NewReader(os.Stdin)
					response, err := reader.ReadString('\n')
					if err != nil {
						return fmt.Errorf("error reading input: %v", err)
					}

					response = strings.TrimSpace(strings.ToLower(response))
					if response != "" && response != "y" && response != "yes" {
						fmt.Println("Upgrade cancelled")
						return nil
					}
				}

				// Perform upgrades
				for _, upgrade := range availableUpgrades {
					fmt.Printf("Updating: %s, %s => %s\n", upgrade.name, upgrade.currentVersion, upgrade.newVersion)

					// Show download progress
					downloadMsg := fmt.Sprintf("ℹ️  Downloading: %s", upgrade.asset.Name)
					fmt.Printf("%s\n", lipgloss.NewStyle().Foreground(lipgloss.Color("14")).Render(downloadMsg))

					// Create temporary directory for extraction
					tempDir := filepath.Join(GetTempDir(), "install-release", "extract", upgrade.name)
					if err := Mkdir(tempDir); err != nil {
						fmt.Printf("Error creating temp directory for %s: %v\n", upgrade.name, err)
						continue
					}
					defer RemoveDir(tempDir)

					// Extract the release
					if err := ExtractRelease(upgrade.asset, tempDir); err != nil {
						fmt.Printf("Error extracting release for %s: %v\n", upgrade.name, err)
						continue
					}

					// Show download complete
					downloadedMsg := fmt.Sprintf("✅ Downloaded: %s", upgrade.asset.Name)
					fmt.Printf("%s\n", lipgloss.NewStyle().Foreground(lipgloss.Color("10")).Render(downloadedMsg))

					// Show extraction progress
					extractMsg := fmt.Sprintf("ℹ️  Extracting: %s", upgrade.asset.Name)
					fmt.Printf("%s\n", lipgloss.NewStyle().Foreground(lipgloss.Color("14")).Render(extractMsg))

					// Find the executable
					executable, err := FindExecutable(tempDir)
					if err != nil {
						fmt.Printf("Error finding executable for %s: %v\n", upgrade.name, err)
						continue
					}

					// Install the executable
					installPath := config.GetPath()
					destPath := filepath.Join(installPath, upgrade.name)
					if err := InstallBin(executable, destPath, false, upgrade.name); err != nil {
						fmt.Printf("Error installing binary for %s: %v\n", upgrade.name, err)
						continue
					}

					// Update state - only store the selected asset (like Python version)
					upgrade.release.Assets = []ReleaseAssets{*upgrade.asset}
					state.SetItem(upgrade.key, upgrade.release)

					// Show success message in bold blue
					successMsg := fmt.Sprintf("Installed: %s", upgrade.name)
					fmt.Printf("%s\n", lipgloss.NewStyle().Foreground(lipgloss.Color("12")).Bold(true).Render(successMsg))
				}
			} else {
				fmt.Printf("All tools are onto latest version\n")
			}

			return nil
		},
	}

	cmd.Flags().BoolVarP(&force, "force", "F", false, "set force")
	cmd.Flags().BoolVarP(&skipPrompt, "skip-prompt", "y", false, "skip confirmation (y/n) prompt")

	return cmd
}

// listCmd represents the list command
func listCmd() *cobra.Command {
	var hold bool

	cmd := &cobra.Command{
		Use:          "ls",
		Short:        "List all installed releases, cli tools",
		Long:         `List all installed tools`,
		SilenceUsage: true,
		RunE: func(cmd *cobra.Command, args []string) error {
			// Load state
			state := NewStateManager()
			if err := state.Load(); err != nil {
				return fmt.Errorf("error loading state: %v", err)
			}

			items := state.Items()
			if len(items) == 0 {
				PrintInfo("No installed tools found")
				return nil
			}

			// Show all tools in one list, regardless of hold flag
			PrintSection("Installed tools")

			// Prepare data for PrintTable
			var tableRows []map[string]string
			for name, release := range items {
				// Show all tools when not using --hold flag, or only held tools when using --hold flag
				if !hold || release.HoldUpdate {
					toolName := name
					if idx := strings.LastIndex(name, "#"); idx != -1 {
						toolName = name[idx+1:]
					}
					repoURL := release.URL
					// Remove URL truncation - always show full URL

					// Add *HOLD_UPDATE* indicator for tools on hold
					version := release.TagName
					if release.HoldUpdate {
						version = version + " *HOLD_UPDATE*"
					}

					tableRows = append(tableRows, map[string]string{
						"Name":       toolName,
						"Version":    version,
						"Repository": repoURL,
					})
				}
			}

			// Sort table rows by name
			sort.Slice(tableRows, func(i, j int) bool {
				return strings.ToLower(tableRows[i]["Name"]) < strings.ToLower(tableRows[j]["Name"])
			})

			headers := []string{"Name", "Version", "Repository"}
			colorFuncs := []func(string) string{
				func(s string) string { return lipgloss.NewStyle().Foreground(lipgloss.Color("11")).Render(s) }, // Light Yellow
				func(s string) string { return lipgloss.NewStyle().Foreground(lipgloss.Color("13")).Render(s) }, // Light Magenta
				func(s string) string { return lipgloss.NewStyle().Foreground(lipgloss.Color("10")).Render(s) }, // Light Green
			}
			PrintTable(tableRows, headers, colorFuncs)
			return nil
		},
	}

	cmd.Flags().BoolVar(&hold, "hold", false, "list of tools which are kept on hold")

	return cmd
}

// removeCmd represents the remove command
func removeCmd() *cobra.Command {
	cmd := &cobra.Command{
		Use:          "rm [NAME]",
		Short:        "Remove any installed releases, cli tools",
		Long:         `Remove an installed tool`,
		Args:         cobra.ExactArgs(1),
		SilenceUsage: true,
		RunE: func(cmd *cobra.Command, args []string) error {
			name := args[0]

			// Load state
			state := NewStateManager()
			if err := state.Load(); err != nil {
				return fmt.Errorf("error loading state: %v", err)
			}

			// Load configuration
			config := NewConfigManager()
			if err := config.Load(); err != nil {
				return fmt.Errorf("error loading config: %v", err)
			}

			// Try to find by tool name using the new methods
			_, key, found := state.GetByName(name)
			if !found {
				return fmt.Errorf("tool %s not found", name)
			}

			// Remove the executable
			installPath := config.GetPath()
			executablePath := filepath.Join(installPath, name)
			if Exists(executablePath) {
				if err := RemoveFile(executablePath); err != nil {
					return fmt.Errorf("error removing executable: %v", err)
				}
			}

			// Remove from state
			state.DelItem(key)

			PrintSuccess("Removed: " + name)
			return nil
		},
	}

	return cmd
}

// configCmd represents the config command
func configCmd() *cobra.Command {
	var token string
	var gitlabToken string
	var path string
	var preRelease bool

	cmd := &cobra.Command{
		Use:          "config",
		Short:        "Set configs for tool",
		Long:         `Configure the tool settings`,
		SilenceUsage: true,
		RunE: func(cmd *cobra.Command, args []string) error {
			// Load configuration
			config := NewConfigManager()
			if err := config.Load(); err != nil {
				return fmt.Errorf("error loading config: %v", err)
			}

			if token != "" {
				config.SetToken(token)
				fmt.Println("Updated GitHub token")
			}

			if gitlabToken != "" {
				config.SetGitlabToken(gitlabToken)
				fmt.Println("Updated GitLab token")
			}

			if path != "" {
				config.SetPath(path)
				fmt.Printf("Updated path to %s\n", path)
			}

			if cmd.Flags().Changed("pre-release") {
				config.SetPreRelease(preRelease)
				if preRelease {
					fmt.Println("Enabled pre-release updates")
				} else {
					fmt.Println("Disabled pre-release updates")
				}
			}

			return nil
		},
	}

	cmd.Flags().StringVar(&token, "token", "", "set your GitHub token to solve API rate-limiting issue")
	cmd.Flags().StringVar(&gitlabToken, "gitlab-token", "", "set your GitLab token to solve API rate-limiting issue")
	cmd.Flags().StringVar(&path, "path", "", "set install path")
	cmd.Flags().BoolVar(&preRelease, "pre-release", false, "Also include pre-releases while checking updates")

	return cmd
}

// stateCmd represents the state command
func stateCmd() *cobra.Command {
	cmd := &cobra.Command{
		Use:          "state",
		Short:        "Show the current stored state",
		Long:         `Show the current state of installed tools`,
		SilenceUsage: true,
		RunE: func(cmd *cobra.Command, args []string) error {
			// Load state
			state := NewStateManager()
			if err := state.Load(); err != nil {
				return fmt.Errorf("error loading state: %v", err)
			}

			items := state.Items()
			if len(items) == 0 {
				fmt.Println("No state found")
				return nil
			}

			fmt.Println("Current state:")
			for name, release := range items {
				fmt.Printf("  %s: %s (%s)\n", name, release.TagName, release.URL)
			}

			return nil
		},
	}

	return cmd
}

// pullCmd represents the pull command
func pullCmd() *cobra.Command {
	var url string
	var override bool

	cmd := &cobra.Command{
		Use:          "pull",
		Short:        "Install tools from a remote state",
		Long:         `Install tools from a remote state file`,
		SilenceUsage: true,
		RunE: func(cmd *cobra.Command, args []string) error {
			if url == "" {
				return fmt.Errorf("URL is required")
			}

			fmt.Printf("Pulling state from: %s\n", url)
			fmt.Println("This feature is not yet implemented in the Go version")

			return nil
		},
	}

	cmd.Flags().StringVar(&url, "url", "", "install tools from the remote state")
	cmd.Flags().BoolVarP(&override, "override", "O", false, "Enable Override local tool version with remote state version")

	return cmd
}

// holdCmd represents the hold command
func holdCmd() *cobra.Command {
	var unset bool

	cmd := &cobra.Command{
		Use:          "hold [NAME]",
		Short:        "Keep updates a tool on hold",
		Long:         `Hold or unhold updates for a specific tool`,
		Args:         cobra.ExactArgs(1),
		SilenceUsage: true,
		RunE: func(cmd *cobra.Command, args []string) error {
			name := args[0]

			// Load state
			state := NewStateManager()
			if err := state.Load(); err != nil {
				return fmt.Errorf("error loading state: %v", err)
			}

			// Check if tool exists using GetByName
			release, _, exists := state.GetByName(name)
			if !exists {
				return fmt.Errorf("tool %s not found", name)
			}

			if unset {
				release.HoldUpdate = false
				fmt.Printf("Unheld updates for %s\n", name)
			} else {
				release.HoldUpdate = true
				fmt.Printf("Held updates for %s\n", name)
			}

			// Update the release in state using the existing key
			_, key, _ := state.GetByName(name)
			state.SetItem(key, release)

			return nil
		},
	}

	cmd.Flags().BoolVar(&unset, "unset", true, "unset from hold")

	return cmd
}

// meCmd represents the me command
func meCmd() *cobra.Command {
	var update bool
	var version bool

	cmd := &cobra.Command{
		Use:          "me",
		Short:        "Update ir tool",
		Long:         `Update the install-release tool itself`,
		SilenceUsage: true,
		RunE: func(cmd *cobra.Command, args []string) error {
			if version {
				fmt.Println("install-release v0.5.2 (Go version)")
				return nil
			}

			if update {
				fmt.Println("Updating install-release...")
				fmt.Println("This feature is not yet implemented in the Go version")
				return nil
			}

			return cmd.Help()
		},
	}

	cmd.Flags().BoolVarP(&update, "upgrade", "U", false, "Update tool, install-release")
	cmd.Flags().BoolVar(&version, "version", false, "print version this tool, install-release")

	return cmd
}
