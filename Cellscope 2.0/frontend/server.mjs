import http from "node:http";
import { readFile } from "node:fs/promises";
import { createReadStream, existsSync, statSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const port = Number.parseInt(process.env.PORT || "5173", 10);
const backendOrigin = process.env.BACKEND_ORIGIN || "http://localhost:8000";

const mimeTypes = new Map([
  [".html", "text/html; charset=utf-8"],
  [".css", "text/css; charset=utf-8"],
  [".js", "application/javascript; charset=utf-8"],
  [".json", "application/json; charset=utf-8"],
  [".svg", "image/svg+xml"],
  [".png", "image/png"],
  [".jpg", "image/jpeg"],
  [".jpeg", "image/jpeg"],
  [".ico", "image/x-icon"],
]);

function sendJson(response, statusCode, payload) {
  response.writeHead(statusCode, { "Content-Type": "application/json; charset=utf-8" });
  response.end(JSON.stringify(payload));
}

async function proxyApi(request, response, pathname) {
  try {
    const body =
      request.method === "GET" || request.method === "HEAD"
        ? undefined
        : await new Promise((resolve, reject) => {
            const chunks = [];
            request.on("data", (chunk) => chunks.push(chunk));
            request.on("end", () => resolve(Buffer.concat(chunks)));
            request.on("error", reject);
          });

    const proxied = await fetch(`${backendOrigin}${pathname}`, {
      method: request.method,
      headers: {
        "content-type": request.headers["content-type"] || "application/json",
      },
      body,
    });

    const headers = {};
    for (const [key, value] of proxied.headers.entries()) {
      if (key.toLowerCase() === "content-length") {
        continue;
      }
      headers[key] = value;
    }

    response.writeHead(proxied.status, headers);
    const proxiedBody = Buffer.from(await proxied.arrayBuffer());
    response.end(proxiedBody);
  } catch (error) {
    sendJson(response, 502, {
      error: "backend_unreachable",
      detail: String(error),
      backendOrigin,
    });
  }
}

function safePathname(urlPathname) {
  if (urlPathname === "/") {
    return "index.html";
  }
  const trimmed = urlPathname.replace(/^\/+/, "");
  return trimmed;
}

function serveStatic(response, relativePath) {
  const filePath = path.join(__dirname, relativePath);
  if (!existsSync(filePath) || statSync(filePath).isDirectory()) {
    return false;
  }

  const extension = path.extname(filePath).toLowerCase();
  response.writeHead(200, {
    "Content-Type": mimeTypes.get(extension) || "application/octet-stream",
    "Cache-Control": "no-store",
  });
  createReadStream(filePath).pipe(response);
  return true;
}

const server = http.createServer(async (request, response) => {
  const requestUrl = new URL(request.url || "/", `http://${request.headers.host}`);
  const pathname = requestUrl.pathname;

  if (pathname.startsWith("/api/")) {
    await proxyApi(request, response, `${pathname}${requestUrl.search}`);
    return;
  }

  if (pathname === "/__frontend/health") {
    sendJson(response, 200, {
      status: "ok",
      app: "cellscope2-frontend",
      backendOrigin,
    });
    return;
  }

  if (serveStatic(response, safePathname(pathname))) {
    return;
  }

  try {
    const indexHtml = await readFile(path.join(__dirname, "index.html"), "utf8");
    response.writeHead(200, {
      "Content-Type": "text/html; charset=utf-8",
      "Cache-Control": "no-store",
    });
    response.end(indexHtml);
  } catch (error) {
    sendJson(response, 500, {
      error: "frontend_boot_failure",
      detail: String(error),
    });
  }
});

server.listen(port, () => {
  console.log(`CellScope 2.0 frontend running on http://localhost:${port}`);
  console.log(`Proxying /api requests to ${backendOrigin}`);
});
