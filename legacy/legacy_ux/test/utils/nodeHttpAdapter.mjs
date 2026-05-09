import http from "http";
import https from "https";
import { URL } from "url";

export default function nodeHttpAdapter(config) {
  return new Promise((resolve, reject) => {
    try {
      const url = new URL(config.url, config.baseURL || undefined);
      const isHttps = url.protocol === "https:";
      const transport = isHttps ? https : http;

      const headers = Object.assign({}, config.headers || {});
      let body = null;
      if (config.data !== undefined && config.data !== null) {
        if (typeof config.data === "string" || Buffer.isBuffer(config.data)) {
          body = config.data;
        } else {
          body = JSON.stringify(config.data);
          if (!headers["Content-Type"] && !headers["content-type"]) {
            headers["Content-Type"] = "application/json;charset=utf-8";
          }
        }
        headers["Content-Length"] = Buffer.byteLength(body);
      }

      const requestOptions = {
        method: (config.method || "get").toUpperCase(),
        hostname: url.hostname,
        port: url.port || (isHttps ? 443 : 80),
        path: `${url.pathname}${url.search}`,
        headers,
        timeout: config.timeout,
      };

      const req = transport.request(requestOptions, (res) => {
        const chunks = [];
        res.on("data", (chunk) => chunks.push(chunk));
        res.on("end", () => {
          const buffer = Buffer.concat(chunks);
          const contentType = res.headers["content-type"] || "";
          let data = buffer.toString();
          if (contentType.includes("application/json")) {
            try {
              data = JSON.parse(data);
            } catch (_e) {
              /* keep raw */
            }
          }

          resolve({
            data,
            status: res.statusCode,
            statusText: res.statusMessage,
            headers: res.headers,
            config,
            request: req,
          });
        });
      });

      req.on("error", (err) => reject(err));
      if (requestOptions.timeout) {
        req.setTimeout(requestOptions.timeout, () => {
          req.abort();
          reject(new Error("timeout"));
        });
      }

      if (body) req.write(body);
      req.end();
    } catch (err) {
      reject(err);
    }
  });
}
