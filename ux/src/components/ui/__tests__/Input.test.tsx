import { describe, it, expect } from "vitest";
import { screen } from "@testing-library/react";
import { render } from "@/test/test-utils";
import { Input, Textarea, Select } from "../Input";

describe("Input", () => {
  describe("CSS class styling", () => {
    it("applies text-input base class", () => {
      render(<Input />);
      expect(screen.getByRole("textbox")).toHaveClass("text-input");
    });

    it("applies text-input--mono class when mono prop is true", () => {
      render(<Input mono />);
      expect(screen.getByRole("textbox")).toHaveClass("text-input--mono");
    });

    it("does not apply mono class when mono prop is false", () => {
      render(<Input mono={false} />);
      expect(screen.getByRole("textbox")).not.toHaveClass("text-input--mono");
    });

    it("combines text-input class with mono class", () => {
      render(<Input mono />);
      const input = screen.getByRole("textbox");
      expect(input).toHaveClass("text-input");
      expect(input).toHaveClass("text-input--mono");
    });

    it("applies text-input--error class when error prop is true", () => {
      render(<Input error />);
      expect(screen.getByRole("textbox")).toHaveClass("text-input--error");
    });
  });

  describe("custom classes", () => {
    it("accepts additional className prop", () => {
      render(<Input className="custom-class" />);
      const input = screen.getByRole("textbox");
      expect(input).toHaveClass("text-input");
      expect(input).toHaveClass("custom-class");
    });

    it("combines all classes together", () => {
      render(<Input mono className="custom-class" />);
      const input = screen.getByRole("textbox");
      expect(input).toHaveClass("text-input");
      expect(input).toHaveClass("text-input--mono");
      expect(input).toHaveClass("custom-class");
    });
  });

  describe("HTML attributes", () => {
    it("renders as input element", () => {
      render(<Input />);
      expect(screen.getByRole("textbox")).toBeInTheDocument();
    });

    it("forwards placeholder attribute", () => {
      render(<Input placeholder="Enter text..." />);
      expect(screen.getByPlaceholderText("Enter text...")).toBeInTheDocument();
    });

    it("forwards disabled attribute", () => {
      render(<Input disabled />);
      expect(screen.getByRole("textbox")).toBeDisabled();
    });
  });
});

describe("Textarea", () => {
  describe("CSS class styling", () => {
    it("applies text-area base class", () => {
      render(<Textarea />);
      expect(screen.getByRole("textbox")).toHaveClass("text-area");
    });

    it("applies text-area--mono class when mono prop is true", () => {
      render(<Textarea mono />);
      expect(screen.getByRole("textbox")).toHaveClass("text-area--mono");
    });

    it("applies text-area--error class when error prop is true", () => {
      render(<Textarea error />);
      expect(screen.getByRole("textbox")).toHaveClass("text-area--error");
    });

    it("combines all classes together", () => {
      render(<Textarea mono />);
      const textarea = screen.getByRole("textbox");
      expect(textarea).toHaveClass("text-area");
      expect(textarea).toHaveClass("text-area--mono");
    });
  });

  describe("custom classes", () => {
    it("accepts additional className prop", () => {
      render(<Textarea className="custom-class" />);
      const textarea = screen.getByRole("textbox");
      expect(textarea).toHaveClass("text-area");
      expect(textarea).toHaveClass("custom-class");
    });
  });

  describe("HTML attributes", () => {
    it("renders as textarea element", () => {
      render(<Textarea />);
      expect(screen.getByRole("textbox")).toBeInTheDocument();
    });

    it("forwards placeholder attribute", () => {
      render(<Textarea placeholder="Enter text..." />);
      expect(screen.getByPlaceholderText("Enter text...")).toBeInTheDocument();
    });

    it("forwards disabled attribute", () => {
      render(<Textarea disabled />);
      expect(screen.getByRole("textbox")).toBeDisabled();
    });

    it("forwards rows attribute", () => {
      render(<Textarea rows={5} />);
      expect(screen.getByRole("textbox")).toHaveAttribute("rows", "5");
    });
  });
});

describe("Select", () => {
  describe("CSS class styling", () => {
    it("applies select base class", () => {
      render(
        <Select>
          <option>Option</option>
        </Select>,
      );
      expect(screen.getByRole("combobox")).toHaveClass("select");
    });

    it("applies select--error class when error prop is true", () => {
      render(
        <Select error>
          <option>Option</option>
        </Select>,
      );
      expect(screen.getByRole("combobox")).toHaveClass("select--error");
    });

    it("combines select class with error class", () => {
      render(
        <Select error>
          <option>Option</option>
        </Select>,
      );
      const select = screen.getByRole("combobox");
      expect(select).toHaveClass("select");
      expect(select).toHaveClass("select--error");
    });
  });

  describe("custom classes", () => {
    it("accepts additional className prop", () => {
      render(
        <Select className="custom-class">
          <option>Option</option>
        </Select>,
      );
      const select = screen.getByRole("combobox");
      expect(select).toHaveClass("select");
      expect(select).toHaveClass("custom-class");
    });
  });

  describe("options", () => {
    it("renders options from children", () => {
      render(
        <Select>
          <option value="opt1">Option 1</option>
          <option value="opt2">Option 2</option>
        </Select>,
      );
      expect(screen.getByText("Option 1")).toBeInTheDocument();
      expect(screen.getByText("Option 2")).toBeInTheDocument();
    });
  });

  describe("HTML attributes", () => {
    it("renders as select element", () => {
      render(
        <Select>
          <option>Option</option>
        </Select>,
      );
      expect(screen.getByRole("combobox")).toBeInTheDocument();
    });

    it("forwards disabled attribute", () => {
      render(
        <Select disabled>
          <option>Option</option>
        </Select>,
      );
      expect(screen.getByRole("combobox")).toBeDisabled();
    });
  });
});
