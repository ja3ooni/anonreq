package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
)

func main() {
	apiKey := os.Getenv("ANONREQ_API_KEY")
	if apiKey == "" {
		apiKey = "test-key-0123456789abcdef"
	}

	payload := map[string]interface{}{
		"model": "gpt-4o",
		"messages": []map[string]string{
			{"role": "user", "content": "Contact me at jane@example.com or call +1-555-987-6543"},
		},
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
		respBody, _ := io.ReadAll(resp.Body)
		fmt.Fprintf(os.Stderr, "Error: HTTP %d\n%s\n", resp.StatusCode, string(respBody))
		os.Exit(1)
	}

	respBody, _ := io.ReadAll(resp.Body)
	var data map[string]interface{}
	json.Unmarshal(respBody, &data)

	content := data["choices"].([]interface{})[0].(map[string]interface{})["message"].(map[string]interface{})["content"].(string)
	fmt.Println("Response:", content)

	if !contains(content, "[EMAIL_1]") || !contains(content, "[PHONE_1]") {
		fmt.Fprintln(os.Stderr, "FAIL: Missing tokens")
		os.Exit(1)
	}
	fmt.Println("PASS: Tokens verified")
}

func contains(s, substr string) bool {
	return len(s) >= len(substr) && containsBytes([]byte(s), []byte(substr))
}

func containsBytes(s, sub []byte) bool {
	return bytes.Contains(s, sub)
}
