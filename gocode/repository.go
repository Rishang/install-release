package main

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"
)

// RepositoryError represents repository operation errors
type RepositoryError struct {
	Message string
}

func (e RepositoryError) Error() string {
	return e.Message
}

// UnsupportedRepositoryError represents unsupported repository errors
type UnsupportedRepositoryError struct {
	Message string
}

func (e UnsupportedRepositoryError) Error() string {
	return e.Message
}

// ApiError represents API errors
type ApiError struct {
	Message string
}

func (e ApiError) Error() string {
	return e.Message
}

// RepoInfo is the interface for repository information
type RepoInfo interface {
	Repository() (*RepositoryInfo, error)
	Release(tagName string, preRelease bool) ([]*Release, error)
}

// GitHubInfo handles GitHub repository operations
type GitHubInfo struct {
	owner    string
	repoName string
	api      string
	token    string
	headers  map[string]string
}

// NewGitHubInfo creates a new GitHub repository handler
func NewGitHubInfo(repoURL, token string) (*GitHubInfo, error) {
	if !strings.Contains(repoURL, "github.com") {
		return nil, &UnsupportedRepositoryError{Message: "Repository URL must contain 'github.com'"}
	}

	// Remove trailing slash
	repoURL = strings.TrimSuffix(repoURL, "/")

	// Parse repository information from URL
	parts := strings.Split(repoURL, "/")
	if len(parts) < 5 {
		return nil, &UnsupportedRepositoryError{Message: "Invalid GitHub repository URL"}
	}

	owner := parts[len(parts)-2]
	repoName := parts[len(parts)-1]

	return &GitHubInfo{
		owner:    owner,
		repoName: repoName,
		api:      fmt.Sprintf("https://api.github.com/repos/%s/%s", owner, repoName),
		token:    token,
		headers: map[string]string{
			"Accept": "application/vnd.github.v3+json",
		},
	}, nil
}

// Repository gets repository information
func (gh *GitHubInfo) Repository() (*RepositoryInfo, error) {
	data, err := gh.req(gh.api)
	if err != nil {
		return nil, err
	}

	var repoInfo RepositoryInfo
	if err := json.Unmarshal(data, &repoInfo); err != nil {
		return nil, fmt.Errorf("error unmarshaling repository info: %v", err)
	}

	return &repoInfo, nil
}

// Release gets release information
func (gh *GitHubInfo) Release(tagName string, preRelease bool) ([]*Release, error) {
	var api string
	var isLatest bool
	if tagName != "" {
		api = fmt.Sprintf("%s/releases/tags/%s", gh.api, tagName)
	} else {
		api = fmt.Sprintf("%s/releases/latest", gh.api)
		isLatest = true
	}

	data, err := gh.req(api)
	if err != nil {
		return nil, err
	}

	var releases []*Release
	if tagName != "" || isLatest {
		// Single release (tag or latest)
		var release Release
		if err := json.Unmarshal(data, &release); err != nil {
			return nil, fmt.Errorf("error unmarshaling release: %v", err)
		}
		// Set the correct repository URL instead of API URL
		release.URL = fmt.Sprintf("https://github.com/%s/%s", gh.owner, gh.repoName)
		releases = append(releases, &release)
	} else {
		// Multiple releases
		if err := json.Unmarshal(data, &releases); err != nil {
			return nil, fmt.Errorf("error unmarshaling releases: %v", err)
		}
		// Set the correct repository URL for all releases
		for i := range releases {
			releases[i].URL = fmt.Sprintf("https://github.com/%s/%s", gh.owner, gh.repoName)
		}
	}

	// Filter by pre-release flag if needed
	if !preRelease {
		filtered := make([]*Release, 0)
		for _, release := range releases {
			if !release.Prerelease {
				filtered = append(filtered, release)
			}
		}
		releases = filtered
	}

	return releases, nil
}

// req makes a request to the GitHub API
func (gh *GitHubInfo) req(url string) ([]byte, error) {
	client := &http.Client{Timeout: 30 * time.Second}

	req, err := http.NewRequest("GET", url, nil)
	if err != nil {
		return nil, fmt.Errorf("error creating request: %v", err)
	}

	// Add headers
	for k, v := range gh.headers {
		req.Header.Set(k, v)
	}

	// Add authentication if token is provided
	if gh.token != "" {
		req.Header.Set("Authorization", "token "+gh.token)
		// Debug prints removed for security
	} else {
		// fmt.Println("DEBUG: No GitHub token provided") // Optionally keep this line commented
	}

	resp, err := client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("request failed: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, &ApiError{Message: fmt.Sprintf("API request failed with status: %d", resp.StatusCode)}
	}

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("error reading response body: %v", err)
	}

	// Check for API error messages
	var errorResp map[string]interface{}
	if err := json.Unmarshal(body, &errorResp); err == nil {
		if message, ok := errorResp["message"].(string); ok {
			return nil, &ApiError{Message: fmt.Sprintf("GitHub API error: %s", message)}
		}
	}

	return body, nil
}

// GitLabInfo handles GitLab repository operations
type GitLabInfo struct {
	owner    string
	repoName string
	api      string
	token    string
	headers  map[string]string
}

// NewGitLabInfo creates a new GitLab repository handler
func NewGitLabInfo(repoURL, token string) (*GitLabInfo, error) {
	if !strings.Contains(repoURL, "gitlab.com") {
		return nil, &UnsupportedRepositoryError{Message: "Repository URL must contain 'gitlab.com'"}
	}

	// Remove trailing slash
	repoURL = strings.TrimSuffix(repoURL, "/")

	// Parse repository information from URL
	parts := strings.Split(repoURL, "/")
	if len(parts) < 5 {
		return nil, &UnsupportedRepositoryError{Message: "Invalid GitLab repository URL"}
	}

	owner := parts[len(parts)-2]
	repoName := parts[len(parts)-1]

	return &GitLabInfo{
		owner:    owner,
		repoName: repoName,
		api:      fmt.Sprintf("https://gitlab.com/api/v4/projects/%s%%2F%s", owner, repoName),
		token:    token,
		headers: map[string]string{
			"Accept": "application/json",
		},
	}, nil
}

// Repository gets repository information
func (gl *GitLabInfo) Repository() (*RepositoryInfo, error) {
	data, err := gl.req(gl.api)
	if err != nil {
		return nil, err
	}

	var repoInfo RepositoryInfo
	if err := json.Unmarshal(data, &repoInfo); err != nil {
		return nil, fmt.Errorf("error unmarshaling repository info: %v", err)
	}

	return &repoInfo, nil
}

// Release gets release information
func (gl *GitLabInfo) Release(tagName string, preRelease bool) ([]*Release, error) {
	var api string
	if tagName != "" {
		api = fmt.Sprintf("%s/releases/%s", gl.api, tagName)
	} else {
		api = fmt.Sprintf("%s/releases", gl.api)
	}

	data, err := gl.req(api)
	if err != nil {
		return nil, err
	}

	var releases []*Release
	if tagName != "" {
		// Single release
		var release Release
		if err := json.Unmarshal(data, &release); err != nil {
			return nil, fmt.Errorf("error unmarshaling release: %v", err)
		}
		// Set the correct repository URL instead of API URL
		release.URL = fmt.Sprintf("https://gitlab.com/%s/%s", gl.owner, gl.repoName)
		releases = append(releases, &release)
	} else {
		// Multiple releases
		if err := json.Unmarshal(data, &releases); err != nil {
			return nil, fmt.Errorf("error unmarshaling releases: %v", err)
		}
		// Set the correct repository URL for all releases
		for i := range releases {
			releases[i].URL = fmt.Sprintf("https://gitlab.com/%s/%s", gl.owner, gl.repoName)
		}
	}

	// Filter by pre-release flag if needed
	if !preRelease {
		filtered := make([]*Release, 0)
		for _, release := range releases {
			if !release.Prerelease {
				filtered = append(filtered, release)
			}
		}
		releases = filtered
	}

	return releases, nil
}

// req makes a request to the GitLab API
func (gl *GitLabInfo) req(url string) ([]byte, error) {
	client := &http.Client{Timeout: 30 * time.Second}

	req, err := http.NewRequest("GET", url, nil)
	if err != nil {
		return nil, fmt.Errorf("error creating request: %v", err)
	}

	// Add headers
	for k, v := range gl.headers {
		req.Header.Set(k, v)
	}

	// Add authentication if token is provided
	if gl.token != "" {
		req.Header.Set("PRIVATE-TOKEN", gl.token)
	}

	resp, err := client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("request failed: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, &ApiError{Message: fmt.Sprintf("API request failed with status: %d", resp.StatusCode)}
	}

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("error reading response body: %v", err)
	}

	return body, nil
}

// GetRepoInfo creates the appropriate repository handler based on URL
func GetRepoInfo(repoURL, token, gitlabToken string) (RepoInfo, error) {
	if strings.Contains(repoURL, "github.com") {
		return NewGitHubInfo(repoURL, token)
	} else if strings.Contains(repoURL, "gitlab.com") {
		return NewGitLabInfo(repoURL, gitlabToken)
	}

	return nil, &UnsupportedRepositoryError{Message: "Unsupported repository type"}
}
