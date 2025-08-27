package main

import (
	"fmt"
	"strings"
	"time"
)

// OsInfo represents operating system information
type OsInfo struct {
	Architecture  []string `json:"architecture"`
	Platform      string   `json:"platform"`
	PlatformWords []string `json:"platform_words"`
}

// RepositoryInfo represents repository information from GitHub/GitLab
type RepositoryInfo struct {
	Name            string `json:"name"`
	FullName        string `json:"full_name"`
	HTMLURL         string `json:"html_url"`
	Description     string `json:"description"`
	Language        string `json:"language"`
	StargazersCount int    `json:"stargazers_count"`
}

// ReleaseAssets represents a release asset (downloadable file)
type ReleaseAssets struct {
	BrowserDownloadURL string    `json:"browser_download_url"`
	ContentType        string    `json:"content_type"`
	CreatedAt          string    `json:"created_at"`
	DownloadCount      int       `json:"download_count"`
	ID                 int       `json:"id"`
	Name               string    `json:"name"`
	NodeID             string    `json:"node_id"`
	Size               int       `json:"size"`
	State              string    `json:"state"`
	UpdatedAt          string    `json:"updated_at"`
	UpdatedAtDT        time.Time `json:"-"`
}

// SizeMB returns the size in megabytes
func (ra *ReleaseAssets) SizeMB() float64 {
	return float64(ra.Size) / 1000000.0
}

// Release represents a GitHub/GitLab release
type Release struct {
	URL         string          `json:"url"`
	Name        string          `json:"name"`
	TagName     string          `json:"tag_name"`
	Prerelease  bool            `json:"prerelease"`
	PublishedAt string          `json:"published_at"`
	Assets      []ReleaseAssets `json:"assets"`
	HoldUpdate  bool            `json:"hold_update,omitempty"`
}

// PublishedDT returns the published date as time.Time
func (r *Release) PublishedDT() (time.Time, error) {
	// Try different date formats commonly used by GitHub and GitLab
	formats := []string{
		"2006-01-02T15:04:05Z",
		"2006-01-02T15:04:05.000Z",
	}

	for _, fmt := range formats {
		if t, err := time.Parse(fmt, r.PublishedAt); err == nil {
			return t, nil
		}
	}

	return time.Time{}, fmt.Errorf("cannot parse date: %s", r.PublishedAt)
}

// ToolConfig represents the configuration for the tool
type ToolConfig struct {
	Token       string `json:"token,omitempty"`
	GitlabToken string `json:"gitlab_token,omitempty"`
	Path        string `json:"path,omitempty"`
	PreRelease  bool   `json:"pre_release,omitempty"`
}

// IrKey represents a key in the state
type IrKey struct {
	Name string
	URL  string
}

// NewIrKey creates a new IrKey from a repository URL and tool name
func NewIrKey(url, name string) *IrKey {
	return &IrKey{
		Name: name,
		URL:  url,
	}
}

// String returns the key in the format "url#name"
func (k *IrKey) String() string {
	return fmt.Sprintf("%s#%s", k.URL, k.Name)
}

// ParseIrKey parses an ir key from a string in format "url#name"
func ParseIrKey(value string) *IrKey {
	parts := strings.Split(value, "#")
	if len(parts) < 2 {
		// If no # found, treat the whole string as the name and URL as empty
		return &IrKey{
			Name: value,
			URL:  "",
		}
	}

	// Everything before the last # is the URL, everything after is the name
	lastHash := strings.LastIndex(value, "#")
	return &IrKey{
		URL:  value[:lastHash],
		Name: value[lastHash+1:],
	}
}

// State represents the state of installed tools
type State map[string]*Release
