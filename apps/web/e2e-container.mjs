import net from "node:net";

// Keep the browser on the app's configured loopback origin while Docker routes to the host.
// This proxy exists only inside the test container and publishes no host port.
const port = Number(process.env.E2E_PROXY_PORT || 3001);
const sockets = new Set();
const proxy = net.createServer(client => {
  const upstream = net.connect({ host: "host.docker.internal", port });
  sockets.add(client); sockets.add(upstream);
  client.pipe(upstream); upstream.pipe(client);
  client.on("error", () => upstream.destroy()); upstream.on("error", () => client.destroy());
  client.on("close", () => { upstream.destroy(); sockets.delete(client); });
  upstream.on("close", () => { client.destroy(); sockets.delete(upstream); });
});
await new Promise(resolve => proxy.listen(port, "127.0.0.1", resolve));
process.env.E2E_BASE_URL = `http://127.0.0.1:${port}`;
try {
  await import("./e2e.mjs");
  if (process.env.E2E_EXTENDED === "1") await import("./e2e-pdf.mjs");
} finally {
  for (const socket of sockets) socket.destroy();
  proxy.close();
}
