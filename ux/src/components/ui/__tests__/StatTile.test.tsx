import { describe, it, expect } from "vitest";
import { screen } from "@testing-library/react";
import { render } from "@/test/test-utils";
import { StatTile } from "../StatTile";

describe("StatTile", () => {
  describe("CSS class styling", () => {
    it("applies stat-tile base class", () => {
      const { container } = render(<StatTile label="Count" value={42} />);
      expect(container.querySelector(".stat-tile")).toBeInTheDocument();
    });

    it("applies color variant class", () => {
      const { container } = render(<StatTile label="Count" value={42} color="cyan" />);
      const stat = container.querySelector(".stat-tile");
      expect(stat).toHaveClass("stat-tile--cyan");
    });

    it("applies default cyan color when color not specified", () => {
      const { container } = render(<StatTile label="Count" value={42} />);
      const stat = container.querySelector(".stat-tile");
      expect(stat).toHaveClass("stat-tile--cyan");
    });

    it("applies violet color variant", () => {
      const { container } = render(<StatTile label="Count" value={42} color="violet" />);
      const stat = container.querySelector(".stat-tile");
      expect(stat).toHaveClass("stat-tile--violet");
    });

    it("applies amber color variant", () => {
      const { container } = render(<StatTile label="Count" value={42} color="amber" />);
      const stat = container.querySelector(".stat-tile");
      expect(stat).toHaveClass("stat-tile--amber");
    });

    it("applies emerald color variant", () => {
      const { container } = render(<StatTile label="Count" value={42} color="emerald" />);
      const stat = container.querySelector(".stat-tile");
      expect(stat).toHaveClass("stat-tile--emerald");
    });
  });

  describe("label element", () => {
    it("renders stat-tile__label class", () => {
      const { container } = render(<StatTile label="Test Label" value={42} />);
      const label = container.querySelector(".stat-tile__label");
      expect(label).toBeInTheDocument();
      expect(label).toHaveTextContent("Test Label");
    });

    it("displays label text", () => {
      render(<StatTile label="Items Count" value={100} />);
      expect(screen.getByText("Items Count")).toBeInTheDocument();
    });
  });

  describe("value element", () => {
    it("renders stat-tile__value class for value", () => {
      const { container } = render(<StatTile label="Count" value={42} />);
      const value = container.querySelector(".stat-tile__value");
      expect(value).toBeInTheDocument();
    });

    it("displays numeric value", () => {
      render(<StatTile label="Count" value={42} />);
      expect(screen.getByText("42")).toBeInTheDocument();
    });

    it("displays string value", () => {
      render(<StatTile label="Status" value="Active" />);
      expect(screen.getByText("Active")).toBeInTheDocument();
    });
  });

  describe("metadata/subtitle", () => {
    it("renders stat-tile__meta class when sub prop is provided", () => {
      const { container } = render(<StatTile label="Count" value={42} sub="Last updated today" />);
      const meta = container.querySelector(".stat-tile__meta");
      expect(meta).toBeInTheDocument();
    });

    it("displays subtitle text", () => {
      render(<StatTile label="Count" value={42} sub="Last updated today" />);
      expect(screen.getByText("Last updated today")).toBeInTheDocument();
    });

    it("does not render meta when sub is not provided", () => {
      const { container } = render(<StatTile label="Count" value={42} />);
      const meta = container.querySelector(".stat-tile__meta");
      expect(meta).not.toBeInTheDocument();
    });
  });

  describe("complete structure", () => {
    it("renders all elements together", () => {
      const { container } = render(
        <StatTile label="Active Users" value={1250} color="emerald" sub="+5% from yesterday" />,
      );
      expect(container.querySelector(".stat-tile")).toBeInTheDocument();
      expect(container.querySelector(".stat-tile__label")).toHaveTextContent("Active Users");
      expect(container.querySelector(".stat-tile__value")).toHaveTextContent("1250");
      expect(container.querySelector(".stat-tile__label-secondary")).toHaveTextContent(
        "+5% from yesterday",
      );
    });
  });
});
