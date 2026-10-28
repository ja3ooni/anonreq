import { spawn } from "node:child_process";

const command = process.argv[2];
if (command !== "dev" && command !== "start") {
  console.error("Usage: node scripts/bind-host.mjs <dev|start>");
  process.exit(1);
}

const host = process.env.HOST?.trim();
if (!host) {
  console.error(
    "HOST is not set. npm run dev and npm run start already bind 127.0.0.1. Set HOST only as an explicit override, and read the warning in web/README.md.",
  );
  process.exit(1);
}

console.warn(
  [
    `WARNING: binding the AnonReq demo UI to ${host}.`,
    "This demo has no login. Route handlers attach ANONREQ_API_KEY and ANONREQ_ADMIN_API_KEY.",
    "Anyone who can reach it can export audit logs, see raw PII through the preview, and spend provider credits.",
    "Do not expose this process. A real login comes after the demo.",
  ].join(" "),
);

const port = process.env.PORT?.trim() || "3000";
const child = spawn("npx", ["next", command, "-H", host, "--port", port], {
  stdio: "inherit",
});
child.on("exit", (code, signal) => {
  if (signal) {
    process.kill(process.pid, signal);
    return;
  }
  process.exit(code ?? 1);
});
