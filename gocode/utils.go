package main

import (
	"archive/tar"
	"archive/zip"
	"compress/gzip"
	"fmt"
	"io"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"time"

	"github.com/charmbracelet/lipgloss"
	"github.com/charmbracelet/lipgloss/table"
)

// Download downloads a file from URL to the specified path
func Download(url, path string) error {
	client := &http.Client{Timeout: 60 * time.Second}

	resp, err := client.Get(url)
	if err != nil {
		return fmt.Errorf("error downloading file: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("download failed with status: %d", resp.StatusCode)
	}

	file, err := os.Create(path)
	if err != nil {
		return fmt.Errorf("error creating file: %v", err)
	}
	defer file.Close()

	_, err = io.Copy(file, resp.Body)
	if err != nil {
		return fmt.Errorf("error writing file: %v", err)
	}

	return nil
}

// Extract extracts an archive file to the specified directory
func Extract(archivePath, extractPath string) error {
	if strings.HasSuffix(archivePath, ".tar.gz") || strings.HasSuffix(archivePath, ".tgz") {
		return extractTarGz(archivePath, extractPath)
	} else if strings.HasSuffix(archivePath, ".zip") {
		return extractZip(archivePath, extractPath)
	} else if strings.HasSuffix(archivePath, ".tar") {
		return extractTar(archivePath, extractPath)
	}

	return fmt.Errorf("unsupported archive format")
}

// extractTarGz extracts a .tar.gz file
func extractTarGz(archivePath, extractPath string) error {
	file, err := os.Open(archivePath)
	if err != nil {
		return fmt.Errorf("error opening archive: %v", err)
	}
	defer file.Close()

	gzr, err := gzip.NewReader(file)
	if err != nil {
		return fmt.Errorf("error creating gzip reader: %v", err)
	}
	defer gzr.Close()

	tr := tar.NewReader(gzr)

	for {
		header, err := tr.Next()
		if err == io.EOF {
			break
		}
		if err != nil {
			return fmt.Errorf("error reading tar: %v", err)
		}

		target := filepath.Join(extractPath, header.Name)

		switch header.Typeflag {
		case tar.TypeDir:
			if err := os.MkdirAll(target, 0755); err != nil {
				return fmt.Errorf("error creating directory: %v", err)
			}
		case tar.TypeReg:
			if err := os.MkdirAll(filepath.Dir(target), 0755); err != nil {
				return fmt.Errorf("error creating directory: %v", err)
			}

			f, err := os.OpenFile(target, os.O_CREATE|os.O_RDWR, os.FileMode(header.Mode))
			if err != nil {
				return fmt.Errorf("error creating file: %v", err)
			}

			if _, err := io.Copy(f, tr); err != nil {
				f.Close()
				return fmt.Errorf("error writing file: %v", err)
			}
			f.Close()
		}
	}

	return nil
}

// extractTar extracts a .tar file
func extractTar(archivePath, extractPath string) error {
	file, err := os.Open(archivePath)
	if err != nil {
		return fmt.Errorf("error opening archive: %v", err)
	}
	defer file.Close()

	tr := tar.NewReader(file)

	for {
		header, err := tr.Next()
		if err == io.EOF {
			break
		}
		if err != nil {
			return fmt.Errorf("error reading tar: %v", err)
		}

		target := filepath.Join(extractPath, header.Name)

		switch header.Typeflag {
		case tar.TypeDir:
			if err := os.MkdirAll(target, 0755); err != nil {
				return fmt.Errorf("error creating directory: %v", err)
			}
		case tar.TypeReg:
			if err := os.MkdirAll(filepath.Dir(target), 0755); err != nil {
				return fmt.Errorf("error creating directory: %v", err)
			}

			f, err := os.OpenFile(target, os.O_CREATE|os.O_RDWR, os.FileMode(header.Mode))
			if err != nil {
				return fmt.Errorf("error creating file: %v", err)
			}

			if _, err := io.Copy(f, tr); err != nil {
				f.Close()
				return fmt.Errorf("error writing file: %v", err)
			}
			f.Close()
		}
	}

	return nil
}

// extractZip extracts a .zip file
func extractZip(archivePath, extractPath string) error {
	reader, err := zip.OpenReader(archivePath)
	if err != nil {
		return fmt.Errorf("error opening zip: %v", err)
	}
	defer reader.Close()

	for _, file := range reader.File {
		path := filepath.Join(extractPath, file.Name)

		if file.FileInfo().IsDir() {
			if err := os.MkdirAll(path, 0755); err != nil {
				return fmt.Errorf("error creating directory: %v", err)
			}
			continue
		}

		if err := os.MkdirAll(filepath.Dir(path), 0755); err != nil {
			return fmt.Errorf("error creating directory: %v", err)
		}

		fileReader, err := file.Open()
		if err != nil {
			return fmt.Errorf("error opening file in zip: %v", err)
		}

		targetFile, err := os.OpenFile(path, os.O_WRONLY|os.O_CREATE|os.O_TRUNC, file.Mode())
		if err != nil {
			fileReader.Close()
			return fmt.Errorf("error creating file: %v", err)
		}

		if _, err := io.Copy(targetFile, fileReader); err != nil {
			fileReader.Close()
			targetFile.Close()
			return fmt.Errorf("error writing file: %v", err)
		}

		fileReader.Close()
		targetFile.Close()
	}

	return nil
}

// Mkdir creates a directory if it doesn't exist
func Mkdir(path string) error {
	return os.MkdirAll(path, 0755)
}

// GetSystemInfo returns information about the current system
func GetSystemInfo() (string, string) {
	os := runtime.GOOS
	arch := runtime.GOARCH

	// Normalize architecture names
	switch arch {
	case "amd64":
		arch = "x86_64"
	case "386":
		arch = "i386"
	case "arm64":
		arch = "aarch64"
	}

	return os, arch
}

// IsExecutable checks if a file is executable
func IsExecutable(path string) bool {
	info, err := os.Stat(path)
	if err != nil {
		return false
	}

	return info.Mode().IsRegular() && (info.Mode()&0111) != 0
}

// IsBinaryExecutable checks if a file is a binary executable by reading its header
func IsBinaryExecutable(path string) bool {
	file, err := os.Open(path)
	if err != nil {
		return false
	}
	defer file.Close()

	// Read the first 16 bytes to check for executable signatures
	header := make([]byte, 16)
	n, err := file.Read(header)
	if err != nil || n < 4 {
		return false
	}

	// Check for common executable formats

	// ELF (Linux/Unix) - starts with 0x7F, 'E', 'L', 'F'
	if n >= 4 && header[0] == 0x7F && header[1] == 'E' && header[2] == 'L' && header[3] == 'F' {
		return true
	}

	// PE (Windows) - starts with 'MZ'
	if n >= 2 && header[0] == 'M' && header[1] == 'Z' {
		return true
	}

	// Mach-O (macOS) - various magic numbers
	if n >= 4 {
		// Mach-O 32-bit: 0xFEEDFACE, 0xCEFAEDFE
		// Mach-O 64-bit: 0xFEEDFACF, 0xCFFAEDFE
		magic := uint32(header[0])<<24 | uint32(header[1])<<16 | uint32(header[2])<<8 | uint32(header[3])
		if magic == 0xFEEDFACE || magic == 0xCEFAEDFE || magic == 0xFEEDFACF || magic == 0xCFFAEDFE {
			return true
		}
	}

	// Check if it starts with a shebang (#!/...) - this is a script, not a binary
	if n >= 2 && header[0] == '#' && header[1] == '!' {
		return false
	}

	// Check if it looks like text (all printable ASCII characters in first few bytes)
	// This helps filter out shell scripts, completion scripts, etc.
	for i := 0; i < n && i < 8; i++ {
		if header[i] < 32 || header[i] > 126 {
			// Contains non-printable characters, likely binary
			// But we need to be more strict about what we consider binary executables
			break
		}
		if i == 7 {
			// First 8 bytes are all printable ASCII, likely a text file
			return false
		}
	}

	return false
}

// FindExecutable finds an executable file in a directory
func FindExecutable(dir string) (string, error) {
	// Use filepath.Walk to search recursively
	var binaryExecutables []string
	var executableFiles []string
	var candidateFiles []string
	var allFiles []string

	err := filepath.Walk(dir, func(path string, info os.FileInfo, err error) error {
		if err != nil {
			return err
		}

		if info.IsDir() {
			return nil
		}

		name := info.Name()
		allFiles = append(allFiles, path)

		// Skip obviously non-executable files
		if strings.HasSuffix(name, ".txt") ||
			strings.HasSuffix(name, ".md") ||
			strings.HasSuffix(name, ".json") ||
			strings.HasSuffix(name, ".yaml") ||
			strings.HasSuffix(name, ".yml") ||
			strings.HasSuffix(name, ".cfg") ||
			strings.HasSuffix(name, ".conf") ||
			strings.HasSuffix(name, ".log") ||
			strings.HasSuffix(name, ".LICENSE") ||
			strings.HasSuffix(name, "LICENSE") ||
			strings.HasSuffix(name, "README") ||
			strings.HasSuffix(name, ".tar.gz") ||
			strings.HasSuffix(name, ".zip") ||
			strings.Contains(name, ".1") { // man pages
			return nil
		}

		// Skip completion scripts and common script directories
		if strings.Contains(path, "completion/") ||
			strings.Contains(path, "/completion/") ||
			strings.HasPrefix(name, "_") { // zsh completion files often start with underscore
			return nil
		}

		// First priority: Files that are binary executables
		if IsBinaryExecutable(path) {
			binaryExecutables = append(binaryExecutables, path)
			return nil
		}

		// Second priority: Files that are executable (may be scripts)
		if IsExecutable(path) {
			executableFiles = append(executableFiles, path)
			return nil
		}

		// Look for files without extensions (typical for Linux binaries)
		if !strings.Contains(filepath.Base(name), ".") {
			candidateFiles = append(candidateFiles, path)
		}

		// Look for files with executable extensions
		if strings.HasSuffix(name, ".exe") ||
			strings.HasSuffix(name, ".bin") ||
			strings.HasSuffix(name, ".app") {
			candidateFiles = append(candidateFiles, path)
		}

		// Look for versioned binary names (e.g., ctop-0.7.7-linux-amd64)
		// These typically contain dashes, version numbers, and platform info
		baseName := filepath.Base(name)
		if strings.Contains(baseName, "-") &&
			(strings.Contains(baseName, "linux") || strings.Contains(baseName, "darwin") || strings.Contains(baseName, "windows") ||
				strings.Contains(baseName, "amd64") || strings.Contains(baseName, "x86_64") || strings.Contains(baseName, "arm64")) {
			candidateFiles = append(candidateFiles, path)
		}

		return nil
	})

	if err != nil {
		return "", fmt.Errorf("error walking directory: %v", err)
	}

	// First priority: Binary executables
	if len(binaryExecutables) > 0 {
		return binaryExecutables[0], nil
	}

	// Second priority: Other executable files (scripts), but validate them first
	for _, path := range executableFiles {
		// Make sure it's not a completion script that somehow got through
		name := filepath.Base(path)
		if !strings.HasPrefix(name, "_") &&
			!strings.Contains(path, "completion") &&
			!strings.Contains(path, "bash_completion") {
			return path, nil
		}
	}

	// Third priority: Candidate files (check if they are binaries)
	for _, path := range candidateFiles {
		if IsBinaryExecutable(path) {
			// Make it executable just in case
			if err := os.Chmod(path, 0755); err != nil {
				return "", fmt.Errorf("error setting executable permissions: %v", err)
			}
			return path, nil
		}
	}

	// Last resort: If we still haven't found anything and there's only one file, check if it's a binary
	if len(allFiles) == 1 {
		if IsBinaryExecutable(allFiles[0]) {
			// Make it executable just in case
			if err := os.Chmod(allFiles[0], 0755); err != nil {
				return "", fmt.Errorf("error setting executable permissions: %v", err)
			}
			return allFiles[0], nil
		}
	}

	return "", fmt.Errorf("no binary executable found in directory")
}

// CopyFile copies a file from src to dst
func CopyFile(src, dst string) error {
	sourceFile, err := os.Open(src)
	if err != nil {
		return fmt.Errorf("error opening source file: %v", err)
	}
	defer sourceFile.Close()

	destFile, err := os.Create(dst)
	if err != nil {
		return fmt.Errorf("error creating destination file: %v", err)
	}
	defer destFile.Close()

	if _, err := io.Copy(destFile, sourceFile); err != nil {
		return fmt.Errorf("error copying file: %v", err)
	}

	// Copy permissions
	sourceInfo, err := sourceFile.Stat()
	if err != nil {
		return fmt.Errorf("error getting source file info: %v", err)
	}

	if err := destFile.Chmod(sourceInfo.Mode()); err != nil {
		return fmt.Errorf("error setting file permissions: %v", err)
	}

	return nil
}

// RemoveFile removes a file
func RemoveFile(path string) error {
	return os.Remove(path)
}

// RemoveDir removes a directory and its contents
func RemoveDir(path string) error {
	return os.RemoveAll(path)
}

// Exists checks if a file or directory exists
func Exists(path string) bool {
	_, err := os.Stat(path)
	return err == nil
}

// GetTempDir returns a temporary directory
func GetTempDir() string {
	return os.TempDir()
}

// RunCommand runs a shell command
func RunCommand(command string, args ...string) error {
	cmd := exec.Command(command, args...)
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	return cmd.Run()
}

// RunCommandWithOutput runs a shell command and returns the output
func RunCommandWithOutput(command string, args ...string) (string, error) {
	cmd := exec.Command(command, args...)
	output, err := cmd.Output()
	if err != nil {
		return "", fmt.Errorf("error running command: %v", err)
	}
	return string(output), nil
}

// PrintTable prints a beautiful table using Lip Gloss with colors and proper styling
func PrintTable(data []map[string]string, headers []string, colorFuncs []func(string) string) {
	if len(headers) == 0 || len(data) == 0 {
		return
	}

	// Define color scheme
	var (
		purple    = lipgloss.Color("99")
		gray      = lipgloss.Color("245")
		lightGray = lipgloss.Color("241")
		white     = lipgloss.Color("15")

		headerStyle  = lipgloss.NewStyle().Foreground(white).Bold(true).Align(lipgloss.Center)
		cellStyle    = lipgloss.NewStyle().Padding(0, 1)
		oddRowStyle  = cellStyle.Foreground(gray)
		evenRowStyle = cellStyle.Foreground(lightGray)
	)

	// Create table with improved styling
	t := table.New().
		Border(lipgloss.RoundedBorder()).
		BorderStyle(lipgloss.NewStyle().Foreground(purple)).
		StyleFunc(func(row, col int) lipgloss.Style {
			switch {
			case row == table.HeaderRow:
				return headerStyle
			case row%2 == 0:
				return evenRowStyle
			default:
				return oddRowStyle
			}
		})

	// Set headers
	t.Headers(headers...)

	// Add rows
	for _, row := range data {
		var rowData []string
		for i, header := range headers {
			value := row[header]
			if colorFuncs != nil && i < len(colorFuncs) && colorFuncs[i] != nil {
				value = colorFuncs[i](value)
			}
			rowData = append(rowData, value)
		}
		t.Row(rowData...)
	}

	fmt.Println(t)
}

// Styled message functions for better UI feedback
var (
	InfoStyle = lipgloss.NewStyle().
			Foreground(lipgloss.Color("14")).
			Bold(true)

	SuccessStyle = lipgloss.NewStyle().
			Foreground(lipgloss.Color("10")).
			Bold(true)

	ErrorStyle = lipgloss.NewStyle().
			Foreground(lipgloss.Color("9")).
			Bold(true)

	SectionStyle = lipgloss.NewStyle().
			Foreground(lipgloss.Color("12")).
			Bold(true)
)

func PrintInfo(message string) {
	fmt.Println(InfoStyle.Render("ℹ️  " + message))
}

func PrintSuccess(message string) {
	fmt.Println(SuccessStyle.Render("✅ " + message))
}

func PrintError(message string) {
	fmt.Println(ErrorStyle.Render("❌ " + message))
}

func PrintSection(message string) {
	fmt.Println(SectionStyle.Render("📋 " + message))
}
