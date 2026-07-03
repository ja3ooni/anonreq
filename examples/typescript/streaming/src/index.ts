const API_KEY = process.env.ANONREQ_API_KEY || "test-key-0123456789abcdef";
const API_URL = "http://localhost:8000/v1/chat/completions";

async function main() {
  const payload = {
    model: "gpt-4o",
    messages: [{ role: "user" as const, content: "Tell me a short story" }],
    stream: true,
  };

  const resp = await fetch(API_URL, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${API_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!resp.ok) {
    console.error(`Error: HTTP ${resp.status}`);
    process.exit(1);
  }

  const reader = resp.body!.pipeThrough(new TextDecoderStream()).getReader();
  let foundDone = false;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    const lines = value.split("\n");
    for (const line of lines) {
      if (line.startsWith("data: ")) {
        const data = line.slice(6);
        if (data === "[DONE]") {
          foundDone = true;
          console.log("data: [DONE]");
        } else {
          console.log(line);
        }
      }
    }
  }

  if (!foundDone) {
    console.error("FAIL: Missing [DONE] event");
    process.exit(1);
  }
  console.log("\nPASS: Streaming completed");
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
