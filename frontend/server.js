// Standalone Next.js server for Azure App Service.
// Serves the pre-built standalone output with explicit static file
// handling, build-time env patching, and proper public file serving.
 
const path = require("path");
const fs = require("fs");
const http = require("http");
 
process.env.NODE_ENV = "production";
process.chdir(__dirname);
 
// Set NEXT_PUBLIC_* env vars so the server-side bundle picks them up
// via real Node.js process.env (not webpack polyfill).
const FEEDBACK_URL = "https://pseg.sharepoint.us/sites/powerplatformteam/_layouts/15/listforms.aspx?cid=NjkxNmE5NzgtMjYyOC00NzE4LTk0M2MtNWRlZWZmMzZmZDg0&nav=OTAyZTBiZTItY2EyYy00M2NkLTgzYzktMTMzMmVjMDIyMTZl";
if (!process.env.NEXT_PUBLIC_FEEDBACK_URL) {
  process.env.NEXT_PUBLIC_FEEDBACK_URL = FEEDBACK_URL;
}
 
// ── 0. Startup diagnostics ──────────────────────────────────────────
console.log("[boot] server.js v4.0 — cwd:", __dirname);
 
const critical = [
  ".next/BUILD_ID",
  ".next/required-server-files.json",
  ".next/server/app/page.js",
  ".next/static",
  "public",
];
for (const f of critical) {
  const full = path.join(__dirname, f);
  const ok = fs.existsSync(full);
  console.log("[boot]", ok ? "  OK" : "  MISSING!", f);
}
 
try {
  const staticDir = path.join(__dirname, ".next", "static");
  const entries = fs.readdirSync(staticDir);
  console.log("[boot] .next/static/ contents:", entries.join(", "));
  if (entries.includes("chunks")) {
    const chunks = fs.readdirSync(path.join(staticDir, "chunks"));
    console.log("[boot] .next/static/chunks/ has", chunks.length, "files");
  }
} catch (e) {
  console.error("[boot] ERROR reading .next/static:", e.message);
}
 
// ── 1. Ensure node_modules is available ──────────────────────────────
const { execSync } = require("child_process");
const NM = path.join(__dirname, "node_modules");
const NM_SAFE = path.join(__dirname, "_node_modules");
 
function hasNextServer() {
  return fs.existsSync(path.join(NM, "next", "dist", "server", "next-server.js"));
}
 
if (hasNextServer()) {
  console.log("[boot] node_modules present with next/dist (ready)");
} else if (fs.existsSync(NM_SAFE)) {
  // Fallback: restore _node_modules (standalone bundle)
  try { fs.rmSync(NM, { recursive: true, force: true }); } catch (_) { }
  fs.renameSync(NM_SAFE, NM);
  console.log("[boot] _node_modules restored to node_modules");
}
 
// If next/dist is still missing, run npm install as last resort
if (!hasNextServer()) {
  console.log("[boot] next/dist missing — running npm install ...");
  try {
    execSync("npm install --production --no-optional", {
      cwd: __dirname,
      stdio: "inherit",
      timeout: 120000,
    });
    console.log("[boot] npm install completed");
  } catch (e) {
    console.error("[boot] npm install failed:", e.message);
    process.exit(1);
  }
}
 
// ── 2. Load & patch config ──────────────────────────────────────────
const sfPath = path.join(__dirname, ".next", "required-server-files.json");
const raw = fs.readFileSync(sfPath, "utf8").replace(/\\\\/g, "/");
const conf = JSON.parse(raw).config;
 
if (conf.experimental) {
  conf.experimental.outputFileTracingRoot = __dirname;
}
 
// Force unoptimized images — next/image will render plain <img> tags
// instead of routing through /_next/image (which needs sharp on Azure).
if (conf.images) {
  conf.images.unoptimized = true;
}
 
process.env.__NEXT_PRIVATE_STANDALONE_CONFIG = JSON.stringify(conf);
 
// ── 3. MIME type map for static files ────────────────────────────────
const MIME = {
  ".js": "application/javascript",
  ".css": "text/css",
  ".json": "application/json",
  ".map": "application/json",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".gif": "image/gif",
  ".svg": "image/svg+xml",
  ".ico": "image/x-icon",
  ".woff": "font/woff",
  ".woff2": "font/woff2",
  ".ttf": "font/ttf",
  ".txt": "text/plain",
};
 
// ── 5. Serve a static file from disk ─────────────────────────────────
function serveStatic(filePath, res) {
  try {
    const resolved = path.resolve(filePath);
    if (!resolved.startsWith(__dirname)) {
      res.statusCode = 403;
      res.end("forbidden");
      return true;
    }
    if (!fs.existsSync(resolved)) return false;
    const stat = fs.statSync(resolved);
    if (!stat.isFile()) return false;
 
    const ext = path.extname(resolved).toLowerCase();
    const mime = MIME[ext] || "application/octet-stream";
 
    res.writeHead(200, {
      "Content-Type": mime,
      "Content-Length": stat.size,
      "Cache-Control": "public, max-age=31536000, immutable",
    });
    fs.createReadStream(resolved).pipe(res);
    return true;
  } catch (_) {
    return false;
  }
}
 
// ── 6. Boot NextServer ──────────────────────────────────────────────
const NextServer = require("next/dist/server/next-server").default;
const currentPort = parseInt(process.env.PORT, 10) || 3000;
const hostname = "0.0.0.0";
 
const nextServer = new NextServer({
  hostname,
  port: currentPort,
  dir: path.join(__dirname),
  dev: false,
  customServer: false,
  conf,
});
 
const nextHandler = nextServer.getRequestHandler();
 
// ── 7. Security headers ──────────────────────────────────────────────
function setSecurityHeaders(res) {
  res.setHeader("Strict-Transport-Security", "max-age=31536000; includeSubDomains");
  res.setHeader("X-Content-Type-Options", "nosniff");
  res.setHeader("X-Frame-Options", "DENY");
  res.setHeader("Referrer-Policy", "strict-origin-when-cross-origin");
  res.setHeader("Permissions-Policy", "camera=(), microphone=(), geolocation=()");
  res.setHeader(
    "Content-Security-Policy",
    [
      "default-src 'self'",
      "script-src 'self' 'unsafe-inline' 'unsafe-eval'",
      "style-src 'self' 'unsafe-inline'",
      "img-src 'self' data: blob:",
      "font-src 'self' data:",
      "connect-src 'self' https://*.microsoftonline.us https://*.microsoftonline.com https://*.microsoft.com " +
        (process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000"),
      "frame-src 'none'",
      "object-src 'none'",
      "base-uri 'self'",
    ].join("; ")
  );
}
 
// ── 8. HTTP server with static file priority ────────────────────────
const server = http.createServer(async (req, res) => {
  try {
    setSecurityHeaders(res);
    const url = req.url || "/";
    const qIdx = url.indexOf("?");
    const pathname = qIdx >= 0 ? url.slice(0, qIdx) : url;
 
    // Serve /_next/static/* directly from .next/static/*
    if (pathname.startsWith("/_next/static/")) {
      const relPath = pathname.slice("/_next/static/".length);
      const filePath = path.join(__dirname, ".next", "static", relPath);
      if (serveStatic(filePath, res)) return;
    }
 
    // Handle /_next/image — serve original file from public/ directly
    // (Next.js image optimizer needs sharp which isn't in standalone)
    if (pathname === "/_next/image") {
      try {
        const params = new URL(url, "http://localhost").searchParams;
        const imgUrl = params.get("url");
        if (imgUrl && imgUrl.startsWith("/")) {
          const imgPath = path.join(__dirname, "public", imgUrl);
          if (serveStatic(imgPath, res)) return;
        }
      } catch (_) { }
    }
 
    // Serve /public/* files (like /pseg-logo.png)
    if (!pathname.startsWith("/_next/") && !pathname.startsWith("/api/")) {
      const publicPath = path.join(__dirname, "public", pathname);
      if (serveStatic(publicPath, res)) return;
    }
 
    // Everything else → Next.js handler
    await nextHandler(req, res);
  } catch (err) {
    console.error(err);
    res.statusCode = 500;
    res.end("internal server error");
  }
});
 
server.listen(currentPort, hostname, (err) => {
  if (err) {
    console.error("Failed to start server", err);
    process.exit(1);
  }
  console.log(
    "[boot] Listening on port",
    currentPort,
    "url: http://" + hostname + ":" + currentPort
  );
});
 
 