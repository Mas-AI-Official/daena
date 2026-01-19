package main

import (
	"fmt"
	"log"

	"github.com/Masoud-Masoori/daena/sdk-go"
)

func main() {
	// Initialize client
	client := daena.NewClient(daena.ClientConfig{
		APIKey:  "your-api-key-here",
		BaseURL: "https://api.daena.ai",
	})

	// Test connection
	fmt.Println("Testing connection...")
	connected, err := client.TestConnection()
	if err != nil {
		log.Fatalf("Connection test failed: %v", err)
	}
	fmt.Printf("✅ Connected: %v\n\n", connected)

	// Get system health
	fmt.Println("Getting system health...")
	health, err := client.GetHealth()
	if err != nil {
		log.Fatalf("Failed to get health: %v", err)
	}
	fmt.Printf("✅ Status: %s\n", health.Status)
	if health.Version != "" {
		fmt.Printf("   Version: %s\n", health.Version)
	}
	fmt.Println()

	// Get system summary
	fmt.Println("Getting system summary...")
	summary, err := client.GetSystemSummary()
	if err != nil {
		log.Fatalf("Failed to get summary: %v", err)
	}
	fmt.Printf("✅ Total Agents: %d\n", summary.TotalAgents)
	fmt.Printf("   Active Agents: %d\n", summary.ActiveAgents)
	fmt.Printf("   Departments: %d\n", summary.Departments)
	fmt.Println()

	// Chat with Daena
	fmt.Println("Chatting with Daena...")
	chatResponse, err := client.Chat("Hello! What can you do?")
	if err != nil {
		log.Fatalf("Chat failed: %v", err)
	}
	fmt.Printf("✅ Response: %s\n", chatResponse.Response)
	fmt.Println()

	// Get all agents
	fmt.Println("Getting all agents...")
	agents, err := client.GetAgents("")
	if err != nil {
		log.Fatalf("Failed to get agents: %v", err)
	}
	fmt.Printf("✅ Found %d agents\n", len(agents))
	if len(agents) > 0 {
		fmt.Printf("   First agent: %s (%s)\n", agents[0].Name, agents[0].Department)
	}
	fmt.Println()

	// Store memory
	fmt.Println("Storing memory...")
	memoryReq := daena.StoreMemoryRequest{
		Key:       "example:test:data",
		ClassName: "example_data",
		Payload: map[string]interface{}{
			"message": "This is a test memory",
			"timestamp": "2025-01-XX",
		},
	}
	memory, err := client.StoreMemory(memoryReq)
	if err != nil {
		log.Fatalf("Failed to store memory: %v", err)
	}
	fmt.Printf("✅ Stored memory: %s\n", memory.RecordID)
	fmt.Printf("   Key: %s\n", memory.Key)
	fmt.Println()

	// Retrieve memory
	fmt.Println("Retrieving memory...")
	retrieved, err := client.RetrieveMemory("example:test:data")
	if err != nil {
		log.Fatalf("Failed to retrieve memory: %v", err)
	}
	fmt.Printf("✅ Retrieved: %s\n", retrieved.Key)
	fmt.Println()

	// Run council debate
	fmt.Println("Running council debate...")
	debateReq := daena.CouncilDebateRequest{
		Department: "product",
		Topic:      "Should we prioritize feature X?",
		Context: map[string]interface{}{
			"budget": 50000,
			"timeline": "Q1 2025",
		},
	}
	decision, err := client.RunCouncilDebate(debateReq)
	if err != nil {
		log.Fatalf("Council debate failed: %v", err)
	}
	fmt.Printf("✅ Decision: %s\n", decision.Decision)
	fmt.Printf("   Confidence: %.2f%%\n", decision.Confidence*100)
	fmt.Println()

	fmt.Println("✅ All operations completed successfully!")
}

