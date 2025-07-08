package main

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
)

// StateManager handles the state of installed tools
type StateManager struct {
	state     State
	stateFile string
}

// NewStateManager creates a new state manager
func NewStateManager() *StateManager {
	stateFile := StatePath()

	// Ensure directory exists
	dir := filepath.Dir(stateFile)
	if err := os.MkdirAll(dir, 0755); err != nil {
		fmt.Printf("Error creating directory %s: %v\n", dir, err)
	}

	return &StateManager{
		state:     make(State),
		stateFile: stateFile,
	}
}

// Load loads the state from file
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

	decoder := json.NewDecoder(file)
	if err := decoder.Decode(&sm.state); err != nil {
		return fmt.Errorf("error decoding state file: %v", err)
	}

	return nil
}

// Save saves the state to file
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

// Get retrieves a value from state
func (sm *StateManager) Get(key string) (*Release, bool) {
	release, exists := sm.state[key]
	return release, exists
}

// Set sets a value in state
func (sm *StateManager) Set(key string, value *Release) {
	sm.state[key] = value
	sm.Save()
}

// Delete removes a value from state
func (sm *StateManager) Delete(key string) {
	delete(sm.state, key)
	sm.Save()
}

// Keys returns all keys in the state
func (sm *StateManager) Keys() []string {
	keys := make([]string, 0, len(sm.state))
	for k := range sm.state {
		keys = append(keys, k)
	}
	return keys
}

// Items returns all items in the state
func (sm *StateManager) Items() map[string]*Release {
	return sm.state
}

// Len returns the number of items in state
func (sm *StateManager) Len() int {
	return len(sm.state)
}

// Has returns true if key exists in state
func (sm *StateManager) Has(key string) bool {
	_, exists := sm.state[key]
	return exists
}
