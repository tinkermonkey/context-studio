import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { downloadJson } from "../download";

describe("downloadJson", () => {
  let clicked: { filename: string; href: string; attached: boolean }[];

  beforeEach(() => {
    vi.useFakeTimers();
    clicked = [];
    vi.spyOn(URL, "createObjectURL").mockReturnValue("blob:file");
    vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => {});
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (
      this: HTMLAnchorElement,
    ) {
      clicked.push({ filename: this.download, href: this.href, attached: this.isConnected });
    });
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("clicks an attached link, then removes it", () => {
    downloadJson("house.bundle.json", { a: 1 });

    expect(clicked).toEqual([{ filename: "house.bundle.json", href: "blob:file", attached: true }]);
    expect(document.querySelector('a[download="house.bundle.json"]')).not.toBeInTheDocument();
  });

  it("revokes the URL on a later tick, not during the click", () => {
    downloadJson("house.bundle.json", { a: 1 });

    expect(URL.revokeObjectURL).not.toHaveBeenCalled();
    vi.runAllTimers();
    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:file");
  });
});
