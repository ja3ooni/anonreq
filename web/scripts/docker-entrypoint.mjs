import { spawn } from "node:child_process";

// Inside the container, listen on every interface so the published port
// can reach the process. The host restriction is the compose publish
// 127.0.0.1:3000:3000, not this bind.
const host = process.env.HOSTNAME?.trim() || "0.0.0.0";
if (host !== "0.0.0.0") {
  console.warn(
    [
      `WARNING: HOSTNAME=${host}.`,
      "The container should listen on 0.0.0.0 so Docker can forward the published port.",
      "Keep the host publish as 127.0.0.1:3000:3000.",
      "Never publish 0.0.0.0:3000. This demo has no login.",
    ].join(" "),
  );
} else {
  console.warn(
    "Listening on 0.0.0.0 inside the container. Keep the host publish at 127.0.0.1:3000:3000. Never publish 0.0.0.0:3000.",
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
