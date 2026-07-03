const API_KEY = process.env.ANONREQ_API_KEY || "test-key-0123456789abcdef";
const API_URL = "http://localhost:8000/v1/chat/completions";

async function main() {
  const payload = {
    model: "gpt-4o",
    messages: [
      {
        role: "user" as const,
        content: "Mein Name ist Hans Müller, wohnhaft in Berliner Straße 42, 10115 Berlin",
      },
    ],
  };

  const resp = await fetch(API_URL, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${API_KEY}`,
      "Content-Type": "application/json",
      "X-AnonReq-Locale": "de-DE",
    },
    body: JSON.stringify(payload),
  });

  if (!resp.ok) {
    console.error(`Error: HTTP ${resp.status}`);
    console.error(await resp.text());
    process.exit(1);
  }

  const data = await resp.json();
  console.log("Response:", data.choices[0].message.content);
  console.log("PASS: German locale detection applied");
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
