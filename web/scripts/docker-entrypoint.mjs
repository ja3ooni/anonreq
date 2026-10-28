import { spawn } from "node:child_process";

const host = process.env.HOSTNAME?.trim() || "127.0.0.1";
if (host !== "127.0.0.1") {
  console.warn(
    [
      `WARNING: HOSTNAME=${host} binds the AnonReq demo UI beyond loopback.`,
      "This demo has no login. Route handlers attach ANONREQ_API_KEY and ANONREQ_ADMIN_API_KEY.",
      "Anyone who can reach it can export audit logs, see raw PII through the preview, and spend provider credits.",
      "Do not expose this container. A real login comes after the demo.",
    ].join(" "),
  );
}

const port = process.env.PORT?.trim() || "3000";
const child = spawn("npx", ["next", "start", "-H", host, "--port", port], {
  stdio: "inherit",
});
child.on("exit", (code, signal) => {
  if (signal) {
    process.kill(process.pid, signal);
    return;
  }
  process.exit(code ?? 1);
});
