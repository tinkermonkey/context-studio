import { describe, it, expect, vi } from "vitest";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { render } from "@/test/test-utils";
import { ListPager } from "../ListPager";

function renderPager(overrides: Partial<Parameters<typeof ListPager>[0]> = {}) {
  const props = {
    total: 208,
    limit: 50,
    offset: 0,
    pageSizes: [50, 100, 250] as const,
    onPageChange: vi.fn(),
    onPageSizeChange: vi.fn(),
    ...overrides,
  };
  render(<ListPager {...props} />);
  return props;
}

describe("ListPager", () => {
  it("renders a navigation landmark with testid and CSS classes", () => {
    renderPager();
    const pager = screen.getByTestId("list-pager");
    expect(pager).toHaveAttribute("role", "navigation");
    expect(pager).toHaveAttribute("aria-label", "Pagination");
    expect(pager).toHaveClass("schema-table-footer", "list-pager");
    expect(screen.getByTestId("list-pager-range")).toHaveClass("list-pager__range");
    expect(screen.getByTestId("list-pager-range")).toHaveAttribute("aria-live", "polite");
  });

  it("shows the row range, total and page position", () => {
    renderPager({ offset: 50 });
    expect(screen.getByTestId("list-pager-range")).toHaveTextContent("51–100 of 208");
    expect(screen.getByTestId("list-pager-page")).toHaveTextContent("Page 2 of 5");
  });

  it("clamps the last page range to the total", () => {
    renderPager({ offset: 200 });
    expect(screen.getByTestId("list-pager-range")).toHaveTextContent("201–208 of 208");
  });

  it("disables Previous on the first page and Next on the last, with aria-disabled", () => {
    renderPager({ offset: 0 });
    expect(screen.getByTestId("list-pager-prev")).toBeDisabled();
    expect(screen.getByTestId("list-pager-prev")).toHaveAttribute("aria-disabled", "true");
    expect(screen.getByTestId("list-pager-next")).not.toBeDisabled();
    expect(screen.getByTestId("list-pager-next")).toHaveAttribute("aria-disabled", "false");
  });

  it("disables Next on the last page", () => {
    renderPager({ offset: 200 });
    expect(screen.getByTestId("list-pager-next")).toBeDisabled();
    expect(screen.getByTestId("list-pager-next")).toHaveAttribute("aria-disabled", "true");
  });

  it("labels the page buttons for assistive tech", () => {
    renderPager({ offset: 50 });
    expect(screen.getByRole("button", { name: "Previous page" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Next page" })).toBeInTheDocument();
  });

  it("requests the next and previous offsets", async () => {
    const props = renderPager({ offset: 50 });
    await userEvent.click(screen.getByTestId("list-pager-next"));
    expect(props.onPageChange).toHaveBeenLastCalledWith(100);
    await userEvent.click(screen.getByTestId("list-pager-prev"));
    expect(props.onPageChange).toHaveBeenLastCalledWith(0);
  });

  it("offers page sizes as a labelled radio group", async () => {
    const props = renderPager();
    const size = screen.getByTestId("list-pager-size");
    expect(size).toHaveAttribute("aria-label", "Rows per page");
    expect(screen.getByRole("radio", { name: "50" })).toHaveAttribute("aria-checked", "true");
    await userEvent.click(screen.getByRole("radio", { name: "100" }));
    expect(props.onPageSizeChange).toHaveBeenCalledWith(100);
  });

  it("hides the size control when no page sizes are given", () => {
    renderPager({ pageSizes: undefined });
    expect(screen.queryByTestId("list-pager-size")).not.toBeInTheDocument();
  });

  it("renders nothing when there are no rows", () => {
    renderPager({ total: 0 });
    expect(screen.queryByTestId("list-pager")).not.toBeInTheDocument();
  });
});
