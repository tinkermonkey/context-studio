/**
 * Test utility to force axios to use MSW-compatible adapters
 */

import type { AxiosInstance } from "axios";

/**
 * Forces an axios instance to use the MSW-compatible HTTP adapter.
 * This must be called after MSW server has started but before making requests.
 */
export function forceMSWCompatibleAdapter(client: AxiosInstance): void {
  // Use a lazy-loading adapter that imports http/https at request time
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  client.defaults.adapter = function mswCompatibleAdapter(config: any) {
    // Import http/https inside the adapter function to ensure MSW patches are applied
    const http = require("http");
    const https = require("https");
    const { URL } = require("url");

    return new Promise((resolve, reject) => {
      try {
        const url = new URL(config.url, config.baseURL || undefined);
        const isHttps = url.protocol === "https:";
        const transport = isHttps ? https : http;

        // Normalize headers
        const headers: Record<string, string> = {};
        if (config.headers) {
          Object.entries(config.headers).forEach(([key, value]) => {
            if (value !== undefined && value !== null) {
              headers[key] = String(value);
            }
          });
        }

        let body: string | Buffer | null = null;

        if (config.data !== undefined && config.data !== null) {
          if (typeof config.data === "string" || Buffer.isBuffer(config.data)) {
            body = config.data;
          } else {
            body = JSON.stringify(config.data);
            if (!headers["Content-Type"] && !headers["content-type"]) {
              headers["Content-Type"] = "application/json;charset=utf-8";
            }
          }
          if (body !== null) {
            headers["Content-Length"] = String(Buffer.byteLength(body));
          }
        }

        const requestOptions = {
          method: (config.method || "get").toUpperCase(),
          hostname: url.hostname,
          port: url.port || (isHttps ? 443 : 80),
          path: `${url.pathname}${url.search}`,
          headers,
          timeout: config.timeout,
        };

        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const req = transport.request(requestOptions, (res: any) => {
          const chunks: Buffer[] = [];
          res.on("data", (chunk: Buffer) => chunks.push(chunk));
          res.on("end", () => {
            const buffer = Buffer.concat(chunks);
            const contentType = res.headers["content-type"] || "";
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            let data: any = buffer.toString();

            if (contentType.includes("application/json")) {
              try {
                data = JSON.parse(data);
              } catch (_e) {
                // keep raw string if JSON parsing fails
              }
            }

            const response = {
              data,
              status: res.statusCode,
              statusText: res.statusMessage || "",
              headers: res.headers,
              config: config,
              request: req,
            };

            resolve(response);
          });
        });

        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        req.on("error", (err: any) => reject(err));

        if (requestOptions.timeout) {
          req.setTimeout(requestOptions.timeout, () => {
            req.destroy();
            reject(new Error("Request timeout"));
          });
        }

        if (body) {
          req.write(body);
        }
        req.end();
      } catch (err) {
        reject(err);
      }
    });
  };
}
