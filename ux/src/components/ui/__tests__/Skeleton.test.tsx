import { describe, it, expect } from "vitest";
import { render } from "@/test/test-utils";
import { Skeleton } from "../Skeleton";

describe("Skeleton", () => {
  describe("rendering", () => {
    it("renders as a div element", () => {
      const { container } = render(<Skeleton />);
      const skeleton = container.firstChild;
      expect(skeleton).toBeInTheDocument();
      expect(skeleton?.nodeName).toBe("DIV");
    });

    it("applies default height of 1em", () => {
      const { container } = render(<Skeleton />);
      const skeleton = container.firstChild as HTMLDivElement;
      expect(skeleton.style.height).toBe("1em");
    });
  });

  describe("width and height styling", () => {
    it("applies custom width", () => {
      const { container } = render(<Skeleton width="100px" />);
      const skeleton = container.firstChild as HTMLDivElement;
      expect(skeleton.style.width).toBe("100px");
    });

    it("applies custom height", () => {
      const { container } = render(<Skeleton height="24px" />);
      const skeleton = container.firstChild as HTMLDivElement;
      expect(skeleton.style.height).toBe("24px");
    });

    it("applies width as number (pixels)", () => {
      const { container } = render(<Skeleton width={200} />);
      const skeleton = container.firstChild as HTMLDivElement;
      expect(skeleton.style.width).toBe("200px");
    });

    it("applies height as number", () => {
      const { container } = render(<Skeleton height={16} />);
      const skeleton = container.firstChild as HTMLDivElement;
      expect(skeleton.style.height).toBe("16px");
    });

    it("applies both width and height", () => {
      const { container } = render(<Skeleton width="150px" height="30px" />);
      const skeleton = container.firstChild as HTMLDivElement;
      expect(skeleton.style.width).toBe("150px");
      expect(skeleton.style.height).toBe("30px");
    });
  });

  describe("CSS variables and animation", () => {
    it("applies canvas background color via CSS variable", () => {
      const { container } = render(<Skeleton />);
      const skeleton = container.firstChild as HTMLDivElement;
      expect(skeleton.style.background).toBe("var(--canvas-bd)");
    });

    it("applies border-radius via CSS variable", () => {
      const { container } = render(<Skeleton />);
      const skeleton = container.firstChild as HTMLDivElement;
      expect(skeleton.style.borderRadius).toBe("var(--radius-md, 6px)");
    });

    it("applies shimmer animation", () => {
      const { container } = render(<Skeleton />);
      const skeleton = container.firstChild as HTMLDivElement;
      expect(skeleton.style.animation).toBe("skeleton-shimmer 1.4s ease infinite");
    });
  });

  describe("custom classes", () => {
    it("accepts className prop", () => {
      const { container } = render(<Skeleton className="custom-class" />);
      const skeleton = container.firstChild as HTMLDivElement;
      expect(skeleton.className).toBe("custom-class");
    });

    it("applies custom class along with inline styles", () => {
      const { container } = render(
        <Skeleton className="custom-class" width="100px" />,
      );
      const skeleton = container.firstChild as HTMLDivElement;
      expect(skeleton.className).toBe("custom-class");
      expect(skeleton.style.width).toBe("100px");
    });
  });

  describe("custom styles", () => {
    it("accepts style prop for additional styles", () => {
      const { container } = render(
        <Skeleton style={{ marginBottom: "8px" }} />,
      );
      const skeleton = container.firstChild as HTMLDivElement;
      expect(skeleton.style.marginBottom).toBe("8px");
    });

    it("merges custom styles with default styles", () => {
      const { container } = render(
        <Skeleton
          width="100px"
          height="20px"
          style={{ marginLeft: "4px" }}
        />,
      );
      const skeleton = container.firstChild as HTMLDivElement;
      expect(skeleton.style.width).toBe("100px");
      expect(skeleton.style.height).toBe("20px");
      expect(skeleton.style.marginLeft).toBe("4px");
    });

    it("allows overriding default styles via style prop", () => {
      const { container } = render(
        <Skeleton height="20px" style={{ borderRadius: "4px" }} />,
      );
      const skeleton = container.firstChild as HTMLDivElement;
      expect(skeleton.style.borderRadius).toBe("4px");
    });
  });

  describe("complete structure", () => {
    it("renders all properties correctly", () => {
      const { container } = render(
        <Skeleton
          width="120px"
          height="24px"
          className="my-skeleton"
          style={{ marginBottom: "8px" }}
        />,
      );
      const skeleton = container.firstChild as HTMLDivElement;
      expect(skeleton.className).toBe("my-skeleton");
      expect(skeleton.style.width).toBe("120px");
      expect(skeleton.style.height).toBe("24px");
      expect(skeleton.style.marginBottom).toBe("8px");
      expect(skeleton.style.background).toBe("var(--canvas-bd)");
    });
  });

  describe("dark mode token tests", () => {
    it("maintains canvas-bd token reference with dark-canvas class", () => {
      document.body.classList.add("dark-canvas");
      const { container } = render(<Skeleton />);
      const skeleton = container.firstChild as HTMLDivElement;
      expect(skeleton.style.background).toBe("var(--canvas-bd)");
      document.body.classList.remove("dark-canvas");
    });
  });
});
