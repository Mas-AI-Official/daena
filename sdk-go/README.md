# Daena AI VP - Go SDK

Official Go client library for the Daena AI VP System.

## Installation

```bash
go get github.com/Masoud-Masoori/daena/sdk-go
```

## Quick Start

```go
package main

import (
    "fmt"
    "github.com/Masoud-Masoori/daena/sdk-go"
)

func main() {
    // Initialize client
    client := daena.NewClient(daena.ClientConfig{
        APIKey:  "your-api-key",
        BaseURL: "https://api.daena.ai",
    })

    // Test connection
    connected, err := client.TestConnection()
    if err != nil {
        panic(err)
    }
    fmt.Printf("Connected: %v\n", connected)

    // Get system health
    health, err := client.GetHealth()
    if err != nil {
        panic(err)
    }
    fmt.Printf("Status: %s\n", health.Status)

    // Chat with Daena
    response, err := client.Chat("Hello Daena!")
    if err != nil {
        panic(err)
    }
    fmt.Printf("Response: %s\n", response.Response)
}
```

## Features

- ✅ Complete API coverage
- ✅ Type-safe models
- ✅ Error handling
- ✅ Authentication
- ✅ Timeout support

## Documentation

See [SDK Documentation](../../docs/SDK_DOCUMENTATION.md) for complete API reference.

## License

See main repository license.

