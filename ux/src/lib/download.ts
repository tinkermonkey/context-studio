/**
 * Save `data` as a pretty-printed JSON file through the browser's download.
 * The link is attached while clicked and the URL revoked on a later tick:
 * Safari and WKWebView can drop a download from a detached link or a URL
 * revoked in the same tick.
 */
export function downloadJson(filename: string, data: unknown): void {
  const blob = new Blob([JSON.stringify(data, null, 2) + "\n"], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.hidden = true;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 0);
}
