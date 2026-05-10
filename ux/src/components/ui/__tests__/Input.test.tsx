import { describe, it, expect } from "vitest";
import { screen } from "@testing-library/react";
import { render } from "@/test/test-utils";
import { Input, Textarea, Select } from "../Input";

describe("Input", () => {
  describe("CSS class styling", () => {
    it("applies input base class", () => {
      render(<Input />);
      expect(screen.getByRole("textbox")).toHaveClass("input");
    });

    it("applies mono class when mono prop is true", () => {
      render(<Input mono />);
      expect(screen.getByRole("textbox")).toHaveClass("mono");
    });

    it("does not apply mono class when mono prop is false", () => {
      render(<Input mono={false} />);
      expect(screen.getByRole("textbox")).not.toHaveClass("mono");
    });

    it("combines input class with mono class", () => {
      render(<Input mono />);
      const input = screen.getByRole("textbox");
      expect(input).toHaveClass("input");
      expect(input).toHaveClass("mono");
    });
  });

  describe("custom classes", () => {
    it("accepts additional className prop", () => {
      render(<Input className="custom-class" />);
      const input = screen.getByRole("textbox");
      expect(input).toHaveClass("input");
      expect(input).toHaveClass("custom-class");
    });

    it("combines all classes together", () => {
      render(<Input mono className="custom-class" />);
      const input = screen.getByRole("textbox");
      expect(input).toHaveClass("input");
      expect(input).toHaveClass("mono");
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
    it("applies input base class", () => {
      render(<Textarea />);
      expect(screen.getByRole("textbox")).toHaveClass("input");
    });

    it("applies textarea class", () => {
      render(<Textarea />);
      expect(screen.getByRole("textbox")).toHaveClass("textarea");
    });

    it("applies mono class when mono prop is true", () => {
      render(<Textarea mono />);
      expect(screen.getByRole("textbox")).toHaveClass("mono");
    });

    it("combines all classes together", () => {
      render(<Textarea mono />);
      const textarea = screen.getByRole("textbox");
      expect(textarea).toHaveClass("input");
      expect(textarea).toHaveClass("textarea");
      expect(textarea).toHaveClass("mono");
    });
  });

  describe("custom classes", () => {
    it("accepts additional className prop", () => {
      render(<Textarea className="custom-class" />);
      const textarea = screen.getByRole("textbox");
      expect(textarea).toHaveClass("input");
      expect(textarea).toHaveClass("textarea");
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
    it("applies input base class", () => {
      render(
        <Select>
          <option>Option</option>
        </Select>,
      );
      expect(screen.getByRole("combobox")).toHaveClass("input");
    });

    it("applies mono class when mono prop is true", () => {
      render(
        <Select mono>
          <option>Option</option>
        </Select>,
      );
      expect(screen.getByRole("combobox")).toHaveClass("mono");
    });

    it("combines all classes together", () => {
      render(
        <Select mono>
          <option>Option</option>
        </Select>,
      );
      const select = screen.getByRole("combobox");
      expect(select).toHaveClass("input");
      expect(select).toHaveClass("mono");
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
      expect(select).toHaveClass("input");
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
