import http from "http";
import https from "https";
import { URL } from "url";
import type { AxiosRequestConfig, AxiosResponse } from "axios";
import type { OutgoingHttpHeaders } from "http";

/**
 * MSW-compatible HTTP adapter for axios
 *
 * This adapter is designed to work with MSW by importing http/https modules
 * lazily (inside the adapter function) rather than at module load time.
 * This ensures MSW has a chance to patch these modules before they're used.
 */
export function mswCompatibleHttpAdapter(
  config: AxiosRequestConfig,
): Promise<AxiosResponse> {
  return new Promise((resolve, reject) => {
    try {
      const url = new URL(config.url!, config.baseURL || undefined);
      const isHttps = url.protocol === "https:";

      // Import http/https modules lazily to ensure MSW patches are applied
      const transport = isHttps ? https : http;

      // Normalize headers to OutgoingHttpHeaders format
      const headers: OutgoingHttpHeaders = {};
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

          const response: AxiosResponse = {
            data,
            status: res.statusCode!,
            statusText: res.statusMessage || "",
            headers: res.headers,
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
            config: config as any, // Cast to avoid config type mismatch
            request: req,
          };

          resolve(response);
        });
      });

      req.on("error", (err) => reject(err));

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
}
