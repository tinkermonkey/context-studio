import { describe, it, expect } from "vitest";
import { screen } from "@testing-library/react";
import { render } from "@/test/test-utils";
import { Chip } from "../Chip";

describe("Chip", () => {
  describe("CSS class styling", () => {
    it("applies chip base class", () => {
      const { container } = render(<Chip>Tag</Chip>);
      const chip = container.querySelector(".chip");
      expect(chip).toBeInTheDocument();
    });

    it("applies color class for cyan variant", () => {
      const { container } = render(<Chip color="cyan">Cyan</Chip>);
      const chip = container.querySelector(".chip");
      expect(chip).toHaveClass("cyan");
    });

    it("applies color class for amber variant", () => {
      const { container } = render(<Chip color="amber">Amber</Chip>);
      const chip = container.querySelector(".chip");
      expect(chip).toHaveClass("amber");
    });

    it("applies color class for violet variant", () => {
      const { container } = render(<Chip color="violet">Violet</Chip>);
      const chip = container.querySelector(".chip");
      expect(chip).toHaveClass("violet");
    });

    it("applies color class for emerald variant", () => {
      const { container } = render(<Chip color="emerald">Emerald</Chip>);
      const chip = container.querySelector(".chip");
      expect(chip).toHaveClass("emerald");
    });

    it("applies color class for rose variant", () => {
      const { container } = render(<Chip color="rose">Rose</Chip>);
      const chip = container.querySelector(".chip");
      expect(chip).toHaveClass("rose");
    });

    it("applies color class for gray variant", () => {
      const { container } = render(<Chip color="gray">Gray</Chip>);
      const chip = container.querySelector(".chip");
      expect(chip).toHaveClass("gray");
    });
  });

  describe("color indicator dot", () => {
    it("renders dot when color is specified", () => {
      const { container } = render(<Chip color="cyan">Cyan</Chip>);
      const dot = container.querySelector(".dot");
      expect(dot).toBeInTheDocument();
    });

    it("does not render dot when color is not specified", () => {
      const { container } = render(<Chip>No color</Chip>);
      const dot = container.querySelector(".dot");
      expect(dot).not.toBeInTheDocument();
    });
  });

  describe("custom classes", () => {
    it("accepts additional className prop", () => {
      const { container } = render(<Chip className="custom">Tag</Chip>);
      const chip = container.querySelector(".chip");
      expect(chip).toHaveClass("custom");
    });

    it("combines chip class with custom class", () => {
      const { container } = render(
        <Chip color="cyan" className="flex items-center">
          Tag
        </Chip>,
      );
      const chip = container.querySelector(".chip");
      expect(chip).toHaveClass("chip");
      expect(chip).toHaveClass("cyan");
      expect(chip).toHaveClass("flex");
      expect(chip).toHaveClass("items-center");
    });
  });

  describe("content", () => {
    it("renders text content", () => {
      render(<Chip>Tag Label</Chip>);
      expect(screen.getByText("Tag Label")).toBeInTheDocument();
    });

    it("renders element children", () => {
      render(
        <Chip>
          <strong>Bold</strong> Text
        </Chip>,
      );
      expect(screen.getByText("Bold")).toBeInTheDocument();
      expect(screen.getByText("Text")).toBeInTheDocument();
    });
  });
});
