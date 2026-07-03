package main

import (
	"bufio"
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"strings"
)

func main() {
	apiKey := os.Getenv("ANONREQ_API_KEY")
	if apiKey == "" {
		apiKey = "test-key-0123456789abcdef"
	}

	payload := map[string]interface{}{
		"model": "gpt-4o",
		"messages": []map[string]string{
			{"role": "user", "content": "Tell me a short story"},
		},
		"stream": true,
	}

	body, _ := json.Marshal(payload)
	req, _ := http.NewRequest("POST", "http://localhost:8000/v1/chat/completions", bytes.NewReader(body))
	req.Header.Set("Authorization", "Bearer "+apiKey)
	req.Header.Set("Content-Type", "application/json")

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error: %v\n", err)
		os.Exit(1)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		fmt.Fprintf(os.Stderr, "Error: HTTP %d\n", resp.StatusCode)
		os.Exit(1)
	}

	scanner := bufio.NewScanner(resp.Body)
	foundDone := false

	for scanner.Scan() {
		line := scanner.Text()
		if strings.HasPrefix(line, "data: ") {
			data := strings.TrimPrefix(line, "data: ")
			if data == "[DONE]" {
				foundDone = true
				fmt.Println("data: [DONE]")
			} else {
				fmt.Println(line)
			}
		}
	}

	if !foundDone {
		fmt.Fprintln(os.Stderr, "FAIL: Missing [DONE] event")
		os.Exit(1)
	}
	fmt.Println("\nPASS: Streaming completed")
}
