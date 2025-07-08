package main

import (
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"strings"
)

// InstallRelease handles the installation of a release
type InstallRelease struct {
	source string
	name   string
}

// NewInstallRelease creates a new install release instance
func NewInstallRelease(source, name string) *InstallRelease {
	return &InstallRelease{
		source: source,
		name:   name,
	}
}

// Install installs the release
func (ir *InstallRelease) Install(local bool, at string) error {
	if at == "" {
		at = BinPath()
	}

	// Ensure the installation directory exists
	if err := Mkdir(at); err != nil {
		return fmt.Errorf("error creating installation directory: %v", err)
	}

	// Determine the destination path
	var destPath string
	if ir.name != "" {
		destPath = filepath.Join(at, ir.name)
	} else {
		// Extract name from source path
		destPath = filepath.Join(at, filepath.Base(ir.source))
	}

	// Copy the executable
	if err := CopyFile(ir.source, destPath); err != nil {
		return fmt.Errorf("error copying executable: %v", err)
	}

	// Make it executable
	if err := os.Chmod(destPath, 0755); err != nil {
		return fmt.Errorf("error setting executable permissions: %v", err)
	}

	fmt.Printf("Installed: %s\n", filepath.Base(destPath))
	return nil
}

// GetRelease finds the best release asset for the current system
func GetRelease(releases []*Release, repoURL string, extraWords []string) (*ReleaseAssets, error) {
	if len(releases) == 0 {
		return nil, fmt.Errorf("no releases found")
	}

	// Get system information
	os, arch := GetSystemInfo()

	// Find the best matching asset
	var bestAsset *ReleaseAssets
	var bestScore float64

	for _, release := range releases {
		for _, asset := range release.Assets {
			score := calculateAssetScore(asset, os, arch, extraWords)
			if score > bestScore {
				bestScore = score
				bestAsset = &asset
			}
		}
	}

	if bestAsset == nil {
		return nil, fmt.Errorf("no suitable asset found for %s/%s", os, arch)
	}

	return bestAsset, nil
}

// calculateAssetScore calculates a score for how well an asset matches the system
func calculateAssetScore(asset ReleaseAssets, os, arch string, extraWords []string) float64 {
	score := 0.0
	name := strings.ToLower(asset.Name)

	// Get platform patterns
	platformPatterns := getPlatformPatterns(os, arch)

	// Add extra words to patterns
	allPatterns := append(platformPatterns, extraWords...)

	// Add archive patterns for better matching
	allPatterns = append(allPatterns, "tar", "zip")

	// Calculate pattern match score
	matchCount := 0
	for _, pattern := range allPatterns {
		if strings.Contains(name, strings.ToLower(pattern)) {
			matchCount++
		}
	}

	if matchCount == 0 {
		return 0.0
	}

	// Base score from pattern matching
	score = float64(matchCount) / float64(len(allPatterns))

	// Apply penalties for other platforms
	score = applyPlatformPenalties(score, asset, os, arch)

	// Apply bonuses and penalties
	score = applyAssetBonusesAndPenalties(score, asset, name)

	return score
}

// applyPlatformPenalties applies heavy penalties for assets targeting other platforms
func applyPlatformPenalties(score float64, asset ReleaseAssets, currentOS, currentArch string) float64 {
	name := strings.ToLower(asset.Name)
	adjustedScore := score

	// Define platform exclusions
	otherPlatforms := map[string][]string{
		"linux":   {"windows", "darwin", "macos", "win32", "win64", ".exe"},
		"darwin":  {"windows", "linux", "win32", "win64", ".exe"},
		"windows": {"linux", "darwin", "macos"},
	}

	otherArchs := map[string][]string{
		"x86_64":  {"arm64", "aarch64", "arm", "i386", "i686"},
		"aarch64": {"x86_64", "amd64", "x64", "i386", "i686"},
	}

	// Heavy penalty for wrong platform
	if exclusions, exists := otherPlatforms[currentOS]; exists {
		for _, platform := range exclusions {
			if strings.Contains(name, platform) {
				adjustedScore *= 0.1 // 90% penalty for wrong platform
				break
			}
		}
	}

	// Penalty for wrong architecture
	if exclusions, exists := otherArchs[currentArch]; exists {
		for _, arch := range exclusions {
			if strings.Contains(name, arch) {
				adjustedScore *= 0.5 // 50% penalty for wrong architecture
				break
			}
		}
	}

	return adjustedScore
}

// getPlatformPatterns returns platform-specific patterns for matching
func getPlatformPatterns(osName, arch string) []string {
	patterns := []string{strings.ToLower(osName)}

	// Architecture aliases
	archAliases := map[string][]string{
		"x86_64":  {"x86", "x64", "amd64", "amd", "x86_64"},
		"aarch64": {"arm64", "aarch64", "arm"},
	}

	// Add architecture patterns
	if aliases, exists := archAliases[arch]; exists {
		patterns = append(patterns, aliases...)
	} else {
		patterns = append(patterns, strings.ToLower(arch))
	}

	return patterns
}

// applyAssetBonusesAndPenalties applies scoring bonuses and penalties
func applyAssetBonusesAndPenalties(score float64, asset ReleaseAssets, name string) float64 {
	adjustedScore := score

	// Strong preference for archives over packages
	if isArchiveAsset(asset) {
		adjustedScore *= 2.0 // 100% bonus for archives
	} else if isPackageAsset(asset) {
		adjustedScore *= 0.3 // 70% penalty for packages (.deb, .rpm, .pkg)
	}

	// Prefer executables or archives
	if isExecutableAsset(asset) || isArchiveAsset(asset) {
		adjustedScore += 0.2
	}

	// Penalty for debug releases
	if strings.Contains(name, "debug") || strings.Contains(name, "dbg") {
		adjustedScore *= 0.8
	}

	// Prefer smaller files (likely single binaries)
	if asset.Size < 100*1024*1024 { // Less than 100MB
		adjustedScore += 0.1
	}

	return adjustedScore
}

// isExecutableAsset checks if an asset is likely an executable
func isExecutableAsset(asset ReleaseAssets) bool {
	name := strings.ToLower(asset.Name)

	// Check for common executable extensions
	execExtensions := []string{".exe", ".bin", ".app"}
	for _, ext := range execExtensions {
		if strings.HasSuffix(name, ext) {
			return true
		}
	}

	// Check for no extension (common for Linux/Unix executables)
	if !strings.Contains(filepath.Base(name), ".") {
		return true
	}

	// Check content type
	if strings.Contains(asset.ContentType, "executable") ||
		strings.Contains(asset.ContentType, "binary") {
		return true
	}

	return false
}

// isArchiveAsset checks if an asset is an archive
func isArchiveAsset(asset ReleaseAssets) bool {
	name := strings.ToLower(asset.Name)
	archiveExtensions := []string{".tar.gz", ".tgz", ".zip", ".tar"}

	for _, ext := range archiveExtensions {
		if strings.HasSuffix(name, ext) {
			return true
		}
	}

	return false
}

// isPackageAsset checks if an asset is a package file
func isPackageAsset(asset ReleaseAssets) bool {
	name := strings.ToLower(asset.Name)
	packageExtensions := []string{".deb", ".rpm", ".pkg", ".msi", ".dmg"}

	for _, ext := range packageExtensions {
		if strings.HasSuffix(name, ext) {
			return true
		}
	}

	return false
}

// ExtractRelease extracts a release asset
func ExtractRelease(asset *ReleaseAssets, extractPath string) error {
	// Show download information using proper info logging
	PrintInfo(fmt.Sprintf("Downloading: %s (%.1f MB)", asset.Name, float64(asset.Size)/1024/1024))

	// Create temporary directory for download
	tempDir := filepath.Join(GetTempDir(), "install-release")
	if err := Mkdir(tempDir); err != nil {
		return fmt.Errorf("error creating temp directory: %v", err)
	}

	// Download the asset
	downloadPath := filepath.Join(tempDir, asset.Name)
	if err := Download(asset.BrowserDownloadURL, downloadPath); err != nil {
		return fmt.Errorf("error downloading asset: %v", err)
	}

	PrintSuccess(fmt.Sprintf("Downloaded: %s", asset.Name))

	// Extract if it's an archive
	if isArchive(asset.Name) {
		PrintInfo(fmt.Sprintf("Extracting: %s", asset.Name))
		if err := Extract(downloadPath, extractPath); err != nil {
			return fmt.Errorf("error extracting asset: %v", err)
		}
	} else {
		// Copy the file directly
		destPath := filepath.Join(extractPath, asset.Name)
		if err := CopyFile(downloadPath, destPath); err != nil {
			return fmt.Errorf("error copying asset: %v", err)
		}
	}

	// Clean up downloaded file
	RemoveFile(downloadPath)

	return nil
}

// isArchive checks if a file is an archive
func isArchive(filename string) bool {
	archiveExtensions := []string{".tar.gz", ".tgz", ".zip", ".tar"}
	for _, ext := range archiveExtensions {
		if strings.HasSuffix(filename, ext) {
			return true
		}
	}
	return false
}

// InstallBin installs a binary file
func InstallBin(src, dest string, local bool, name string) error {
	// Ensure destination directory exists
	destDir := filepath.Dir(dest)
	if err := Mkdir(destDir); err != nil {
		return fmt.Errorf("error creating destination directory: %v", err)
	}

	// Copy the file
	if err := CopyFile(src, dest); err != nil {
		return fmt.Errorf("error copying binary: %v", err)
	}

	// Make it executable
	if err := os.Chmod(dest, 0755); err != nil {
		return fmt.Errorf("error setting executable permissions: %v", err)
	}

	fmt.Printf("Installed: %s\n", filepath.Base(dest))
	return nil
}

// FindBestAsset finds the best asset for the current system
func FindBestAsset(assets []ReleaseAssets, os, arch string, extraWords []string) *ReleaseAssets {
	var bestAsset *ReleaseAssets
	var bestScore float64

	for _, asset := range assets {
		score := calculateAssetScore(asset, os, arch, extraWords)
		if score > bestScore {
			bestScore = score
			bestAsset = &asset
		}
	}

	return bestAsset
}

// GetExecutablePattern returns a regex pattern for finding executables
func GetExecutablePattern() *regexp.Regexp {
	return regexp.MustCompile(`application/x-(\w+-)?(executable|binary)`)
}

// IsExecutableMimeType checks if a MIME type indicates an executable
func IsExecutableMimeType(mimeType string) bool {
	pattern := GetExecutablePattern()
	return pattern.MatchString(mimeType)
}

// GetExceptionCompressedMimeTypes returns MIME types that are exceptions
func GetExceptionCompressedMimeTypes() []string {
	return []string{
		"application/x-7z-compressed",
	}
}
