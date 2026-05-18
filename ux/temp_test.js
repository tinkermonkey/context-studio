const { render, screen } = require("@testing-library/react");
const { describe, it, expect, vi } = require("vitest");
const React = require("react");
const Sidebar = require("./src/components/shell/Sidebar").Sidebar;

// Mock router
let mockPathname = "/app";
vi.mock("@tanstack/react-router", () => ({
  useNavigate: () => vi.fn(),
  useRouterState: () => ({ location: { pathname: mockPathname } }),
}));

describe("Debug test", () => {
  it("should show what attributes are present", () => {
    render(React.createElement(Sidebar));
    const dashboardItem = screen.getByTestId("sidebar-item-dashboard");
    console.log("Dashboard item HTML:", dashboardItem.outerHTML);
    console.log("aria-current attribute:", dashboardItem.getAttribute("aria-current"));
    console.log("className:", dashboardItem.className);
  });
});
