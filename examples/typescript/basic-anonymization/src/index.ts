const API_KEY = process.env.ANONREQ_API_KEY || "test-key-0123456789abcdef";
const API_URL = "http://localhost:8000/v1/chat/completions";

async function main() {
  const payload = {
    model: "gpt-4o",
    messages: [
      {
        role: "user" as const,
        content: "Contact me at jane@example.com or call +1-555-987-6543",
      },
    ],
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
    console.error(await resp.text());
    process.exit(1);
  }

  const data = await resp.json();
  const content: string = data.choices[0].message.content;
  console.log("Response:", JSON.stringify(data, null, 2));

  if (!content.includes("[EMAIL_1]") || !content.includes("[PHONE_1]")) {
    console.error("FAIL: Missing tokens in response");
    process.exit(1);
  }
  console.log("PASS: Tokens verified");
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
