package main

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
)

// ConfigManager handles the configuration for the tool
type ConfigManager struct {
	config     *ToolConfig
	configFile string
}

// ConfigWrapper represents the Python-style config structure
type ConfigWrapper struct {
	Config *ToolConfig `json:"config"`
}

// NewConfigManager creates a new config manager
func NewConfigManager() *ConfigManager {
	configFile := ConfigPath()

	// Ensure directory exists
	dir := filepath.Dir(configFile)
	if err := os.MkdirAll(dir, 0755); err != nil {
		fmt.Printf("Error creating directory %s: %v\n", dir, err)
	}

	return &ConfigManager{
		config:     &ToolConfig{},
		configFile: configFile,
	}
}

// Load loads the configuration from file
func (cm *ConfigManager) Load() error {
	if _, err := os.Stat(cm.configFile); os.IsNotExist(err) {
		// File doesn't exist, start with default config
		return nil
	}

	file, err := os.Open(cm.configFile)
	if err != nil {
		return fmt.Errorf("error opening config file: %v", err)
	}
	defer file.Close()

	// Try to decode as Python-style config first
	var wrapper ConfigWrapper
	decoder := json.NewDecoder(file)
	if err := decoder.Decode(&wrapper); err == nil && wrapper.Config != nil {
		// Python-style config found
		cm.config = wrapper.Config
		return nil
	}

	// Reset file pointer and try direct decoding
	file.Seek(0, 0)
	decoder = json.NewDecoder(file)
	if err := decoder.Decode(cm.config); err != nil {
		return fmt.Errorf("error decoding config file: %v", err)
	}

	return nil
}

// Save saves the configuration to file
func (cm *ConfigManager) Save() error {
	file, err := os.Create(cm.configFile)
	if err != nil {
		return fmt.Errorf("error creating config file: %v", err)
	}
	defer file.Close()

	encoder := json.NewEncoder(file)
	encoder.SetIndent("", "  ")
	if err := encoder.Encode(cm.config); err != nil {
		return fmt.Errorf("error encoding config: %v", err)
	}

	return nil
}

// GetToken returns the GitHub token
func (cm *ConfigManager) GetToken() string {
	return cm.config.Token
}

// SetToken sets the GitHub token
func (cm *ConfigManager) SetToken(token string) {
	cm.config.Token = token
	cm.Save()
}

// GetGitlabToken returns the GitLab token
func (cm *ConfigManager) GetGitlabToken() string {
	return cm.config.GitlabToken
}

// SetGitlabToken sets the GitLab token
func (cm *ConfigManager) SetGitlabToken(token string) {
	cm.config.GitlabToken = token
	cm.Save()
}

// GetPath returns the installation path
func (cm *ConfigManager) GetPath() string {
	if cm.config.Path == "" {
		return BinPath()
	}
	return cm.config.Path
}

// SetPath sets the installation path
func (cm *ConfigManager) SetPath(path string) {
	cm.config.Path = path
	cm.Save()
}

// GetPreRelease returns the pre-release flag
func (cm *ConfigManager) GetPreRelease() bool {
	return cm.config.PreRelease
}

// SetPreRelease sets the pre-release flag
func (cm *ConfigManager) SetPreRelease(preRelease bool) {
	cm.config.PreRelease = preRelease
	cm.Save()
}

// GetConfig returns the entire config
func (cm *ConfigManager) GetConfig() *ToolConfig {
	return cm.config
}
