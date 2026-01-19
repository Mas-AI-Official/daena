package daena

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"
)

// DaenaClient is the main client for interacting with the Daena AI VP API
type DaenaClient struct {
	apiKey  string
	baseURL string
	client  *http.Client
}

// ClientConfig holds configuration for the Daena client
type ClientConfig struct {
	APIKey  string
	BaseURL string
	Timeout time.Duration
}

// NewClient creates a new Daena client instance
func NewClient(config ClientConfig) *DaenaClient {
	if config.BaseURL == "" {
		config.BaseURL = "https://api.daena.ai"
	}
	if config.Timeout == 0 {
		config.Timeout = 30 * time.Second
	}

	return &DaenaClient{
		apiKey:  config.APIKey,
		baseURL: config.BaseURL,
		client: &http.Client{
			Timeout: config.Timeout,
		},
	}
}

// TestConnection tests the connection to the Daena API
func (c *DaenaClient) TestConnection() (bool, error) {
	req, err := http.NewRequest("GET", fmt.Sprintf("%s/health", c.baseURL), nil)
	if err != nil {
		return false, err
	}

	req.Header.Set("Authorization", fmt.Sprintf("Bearer %s", c.apiKey))
	req.Header.Set("Content-Type", "application/json")

	resp, err := c.client.Do(req)
	if err != nil {
		return false, err
	}
	defer resp.Body.Close()

	return resp.StatusCode == http.StatusOK, nil
}

// GetHealth retrieves the health status of the system
func (c *DaenaClient) GetHealth() (*HealthResponse, error) {
	var health HealthResponse
	err := c.get("/health", &health)
	return &health, err
}

// GetSystemSummary retrieves the system summary
func (c *DaenaClient) GetSystemSummary() (*SystemSummary, error) {
	var summary SystemSummary
	err := c.get("/api/v1/system/summary", &summary)
	return &summary, err
}

// Chat sends a message to Daena and receives a response
func (c *DaenaClient) Chat(message string) (*ChatResponse, error) {
	payload := ChatRequest{
		Message: message,
	}

	var response ChatResponse
	err := c.post("/api/v1/daena/chat", payload, &response)
	return &response, err
}

// GetAgents retrieves all agents or filters by department
func (c *DaenaClient) GetAgents(departmentID string) ([]Agent, error) {
	url := "/api/v1/agents"
	if departmentID != "" {
		url += "?department_id=" + departmentID
	}

	var agents []Agent
	err := c.get(url, &agents)
	return agents, err
}

// GetAgent retrieves a specific agent by ID
func (c *DaenaClient) GetAgent(agentID string) (*Agent, error) {
	var agent Agent
	err := c.get(fmt.Sprintf("/api/v1/agents/%s", agentID), &agent)
	return &agent, err
}

// StoreMemory stores a memory record in NBMF
func (c *DaenaClient) StoreMemory(req StoreMemoryRequest) (*MemoryRecord, error) {
	var record MemoryRecord
	err := c.post("/api/v1/memory/store", req, &record)
	return &record, err
}

// RetrieveMemory retrieves a memory record by key
func (c *DaenaClient) RetrieveMemory(key string) (*MemoryRecord, error) {
	var record MemoryRecord
	err := c.get(fmt.Sprintf("/api/v1/memory/retrieve?key=%s", key), &record)
	return &record, err
}

// SearchMemory searches for memories matching a query
func (c *DaenaClient) SearchMemory(query string, limit int) ([]MemoryRecord, error) {
	if limit == 0 {
		limit = 10
	}

	url := fmt.Sprintf("/api/v1/memory/search?query=%s&limit=%d", query, limit)
	var records []MemoryRecord
	err := c.get(url, &records)
	return records, err
}

// RunCouncilDebate runs a council debate for a department
func (c *DaenaClient) RunCouncilDebate(req CouncilDebateRequest) (*CouncilDecision, error) {
	var decision CouncilDecision
	err := c.post("/api/v1/council/debate", req, &decision)
	return &decision, err
}

// Helper methods for HTTP requests

func (c *DaenaClient) get(endpoint string, result interface{}) error {
	req, err := http.NewRequest("GET", c.baseURL+endpoint, nil)
	if err != nil {
		return err
	}

	req.Header.Set("Authorization", fmt.Sprintf("Bearer %s", c.apiKey))
	req.Header.Set("Content-Type", "application/json")

	resp, err := c.client.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 400 {
		return parseError(resp)
	}

	return json.NewDecoder(resp.Body).Decode(result)
}

func (c *DaenaClient) post(endpoint string, payload interface{}, result interface{}) error {
	body, err := json.Marshal(payload)
	if err != nil {
		return err
	}

	req, err := http.NewRequest("POST", c.baseURL+endpoint, bytes.NewBuffer(body))
	if err != nil {
		return err
	}

	req.Header.Set("Authorization", fmt.Sprintf("Bearer %s", c.apiKey))
	req.Header.Set("Content-Type", "application/json")

	resp, err := c.client.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 400 {
		return parseError(resp)
	}

	return json.NewDecoder(resp.Body).Decode(result)
}

func parseError(resp *http.Response) error {
	body, _ := io.ReadAll(resp.Body)
	return fmt.Errorf("API error (status %d): %s", resp.StatusCode, string(body))
}

