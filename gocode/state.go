package main

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
)

// StateManager handles the state of installed tools - matches Python State class
type StateManager struct {
	state     State
	stateFile string
}

// NewStateManager creates a new state manager - matches Python State.__init__
func NewStateManager() *StateManager {
	stateFile := StatePath()

	// Ensure directory exists - matches Python platform_path behavior
	dir := filepath.Dir(stateFile)
	if err := os.MkdirAll(dir, 0755); err != nil {
		fmt.Printf("Error creating directory %s: %v\n", dir, err)
	}

	sm := &StateManager{
		state:     make(State),
		stateFile: stateFile,
	}

	// Auto-load like Python version
	sm.Load()

	return sm
}

// Load loads the state from file - matches Python State.load()
func (sm *StateManager) Load() error {
	if _, err := os.Stat(sm.stateFile); os.IsNotExist(err) {
		// File doesn't exist, start with empty state
		return nil
	}

	file, err := os.Open(sm.stateFile)
	if err != nil {
		return fmt.Errorf("error opening state file: %v", err)
	}
	defer file.Close()

	// Load as raw JSON first
	var rawState map[string]interface{}
	decoder := json.NewDecoder(file)
	if err := decoder.Decode(&rawState); err != nil {
		return fmt.Errorf("error decoding state file: %v", err)
	}

	// Convert to proper Release objects (like Python FilterDataclass)
	for key, value := range rawState {
		if valueMap, ok := value.(map[string]interface{}); ok {
			release := &Release{}

			// Manual mapping to match Python dataclass filtering
			if url, ok := valueMap["url"].(string); ok {
				release.URL = url
			}
			if name, ok := valueMap["name"].(string); ok {
				release.Name = name
			}
			if tagName, ok := valueMap["tag_name"].(string); ok {
				release.TagName = tagName
			}
			if prerelease, ok := valueMap["prerelease"].(bool); ok {
				release.Prerelease = prerelease
			}
			if publishedAt, ok := valueMap["published_at"].(string); ok {
				release.PublishedAt = publishedAt
			}
			if holdUpdate, ok := valueMap["hold_update"].(bool); ok {
				release.HoldUpdate = holdUpdate
			}

			// Handle assets array
			if assetsInterface, ok := valueMap["assets"].([]interface{}); ok {
				var assets []ReleaseAssets
				for _, assetInterface := range assetsInterface {
					if assetMap, ok := assetInterface.(map[string]interface{}); ok {
						asset := ReleaseAssets{}

						// Map asset fields
						if url, ok := assetMap["browser_download_url"].(string); ok {
							asset.BrowserDownloadURL = url
						}
						if contentType, ok := assetMap["content_type"].(string); ok {
							asset.ContentType = contentType
						}
						if createdAt, ok := assetMap["created_at"].(string); ok {
							asset.CreatedAt = createdAt
						}
						if downloadCount, ok := assetMap["download_count"].(float64); ok {
							asset.DownloadCount = int(downloadCount)
						}
						if id, ok := assetMap["id"].(float64); ok {
							asset.ID = int(id)
						}
						if name, ok := assetMap["name"].(string); ok {
							asset.Name = name
						}
						if nodeID, ok := assetMap["node_id"].(string); ok {
							asset.NodeID = nodeID
						}
						if size, ok := assetMap["size"].(float64); ok {
							asset.Size = int(size)
						}
						if state, ok := assetMap["state"].(string); ok {
							asset.State = state
						}
						if updatedAt, ok := assetMap["updated_at"].(string); ok {
							asset.UpdatedAt = updatedAt
						}

						assets = append(assets, asset)
					}
				}
				release.Assets = assets
			}

			sm.state[key] = release
		}
	}

	return nil
}

// Save saves the state to file - matches Python State.save()
func (sm *StateManager) Save() error {
	file, err := os.Create(sm.stateFile)
	if err != nil {
		return fmt.Errorf("error creating state file: %v", err)
	}
	defer file.Close()

	encoder := json.NewEncoder(file)
	encoder.SetIndent("", "  ")
	if err := encoder.Encode(sm.state); err != nil {
		return fmt.Errorf("error encoding state: %v", err)
	}

	return nil
}

// Get retrieves a value from state - matches Python State.get()
func (sm *StateManager) Get(key string) *Release {
	return sm.state[key] // Returns nil if not found, like Python .get()
}

// Set sets a value in state - matches Python State.set() (no auto-save)
func (sm *StateManager) Set(key string, value *Release) {
	sm.state[key] = value
	// No auto-save here, like Python version
}

// Items returns all items in the state - matches Python State.items()
func (sm *StateManager) Items() map[string]*Release {
	return sm.state
}

// Keys returns all keys in the state - matches Python State.keys()
func (sm *StateManager) Keys() []string {
	keys := make([]string, 0, len(sm.state))
	for k := range sm.state {
		keys = append(keys, k)
	}
	return keys
}

// Pop removes and returns a value from state - matches Python State.pop()
func (sm *StateManager) Pop(key string) *Release {
	value := sm.state[key]
	delete(sm.state, key)
	return value
}

// SetItem sets a value and auto-saves - matches Python State.__setitem__
func (sm *StateManager) SetItem(key string, value *Release) {
	sm.state[key] = value
	sm.Save() // Auto-save like Python __setitem__
}

// DelItem removes a value and auto-saves - matches Python State.__delitem__
func (sm *StateManager) DelItem(key string) {
	delete(sm.state, key)
	sm.Save() // Auto-save like Python __delitem__
}

// Contains checks if key exists - matches Python State.__contains__
func (sm *StateManager) Contains(key string) bool {
	_, exists := sm.state[key]
	return exists
}

// Len returns the number of items - matches Python State.__len__
func (sm *StateManager) Len() int {
	return len(sm.state)
}

// GetByName retrieves a value from state by tool name using IrKey - matches Python usage
func (sm *StateManager) GetByName(name string) (*Release, string, bool) {
	for key, release := range sm.state {
		irKey := ParseIrKey(key)
		if irKey.Name == name {
			return release, key, true
		}
	}
	return nil, "", false
}

// SetByName sets a value in state using IrKey format and auto-saves
func (sm *StateManager) SetByName(url, name string, value *Release) {
	key := NewIrKey(url, name).String()
	sm.SetItem(key, value) // Use SetItem for auto-save
}

// DeleteByName removes a value from state by tool name and auto-saves
func (sm *StateManager) DeleteByName(name string) bool {
	for key := range sm.state {
		irKey := ParseIrKey(key)
		if irKey.Name == name {
			sm.DelItem(key) // Use DelItem for auto-save
			return true
		}
	}
	return false
}
