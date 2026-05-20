import { describe, it, expect } from "vitest";
import { screen } from "@testing-library/react";
import { render } from "@/test/test-utils";
import { TextInput, TextArea, Select } from "@tinkermonkey/heimdall-ui";

describe("Heimdall TextInput", () => {
  describe("data-testid attributes", () => {
    it("renders with data-testid when provided", () => {
      render(<TextInput data-testid="test-input" />);
      expect(screen.getByTestId("test-input")).toBeInTheDocument();
    });

    it("renders without data-testid when not provided", () => {
      render(<TextInput />);
      const input = screen.getByRole("textbox");
      expect(input.getAttribute("data-testid")).toBeNull();
    });
  });

  describe("CSS class styling", () => {
    it("renders as input element", () => {
      render(<TextInput />);
      expect(screen.getByRole("textbox")).toBeInTheDocument();
    });

    it("applies className prop", () => {
      render(<TextInput className="custom-input" />);
      const input = screen.getByRole("textbox");
      expect(input).toHaveClass("custom-input");
    });

    it("combines multiple className values", () => {
      render(<TextInput className="class1 class2" />);
      const input = screen.getByRole("textbox");
      expect(input).toHaveClass("class1");
      expect(input).toHaveClass("class2");
    });
  });

  describe("ARIA roles and attributes", () => {
    it("has textbox role", () => {
      render(<TextInput />);
      expect(screen.getByRole("textbox")).toBeInTheDocument();
    });

    it("forwards aria-label attribute", () => {
      render(<TextInput aria-label="Username" />);
      expect(screen.getByLabelText("Username")).toBeInTheDocument();
    });

    it("forwards aria-describedby attribute", () => {
      render(<TextInput aria-describedby="help-text" />);
      expect(screen.getByRole("textbox")).toHaveAttribute("aria-describedby", "help-text");
    });

    it("is not disabled by default", () => {
      render(<TextInput />);
      expect(screen.getByRole("textbox")).not.toBeDisabled();
    });

    it("is disabled when disabled prop is true", () => {
      render(<TextInput disabled />);
      expect(screen.getByRole("textbox")).toBeDisabled();
    });

    it("is readonly when readonly prop is true", () => {
      render(<TextInput readOnly />);
      expect(screen.getByRole("textbox")).toHaveAttribute("readonly");
    });
  });

  describe("HTML attributes", () => {
    it("forwards placeholder attribute", () => {
      render(<TextInput placeholder="Enter text..." />);
      expect(screen.getByPlaceholderText("Enter text...")).toBeInTheDocument();
    });

    it("forwards type attribute", () => {
      render(<TextInput type="email" />);
      expect(screen.getByRole("textbox")).toHaveAttribute("type", "email");
    });

    it("forwards value attribute", () => {
      render(<TextInput value="test value" readOnly />);
      expect(screen.getByDisplayValue("test value")).toBeInTheDocument();
    });

    it("forwards required attribute", () => {
      render(<TextInput required />);
      expect(screen.getByRole("textbox")).toHaveAttribute("required");
    });

    it("forwards id attribute", () => {
      render(<TextInput id="username-input" />);
      expect(screen.getByRole("textbox")).toHaveAttribute("id", "username-input");
    });

    it("forwards name attribute", () => {
      render(<TextInput name="username" />);
      expect(screen.getByRole("textbox")).toHaveAttribute("name", "username");
    });
  });
});

describe("Heimdall TextArea", () => {
  describe("data-testid attributes", () => {
    it("renders with data-testid when provided", () => {
      render(<TextArea data-testid="test-textarea" />);
      expect(screen.getByTestId("test-textarea")).toBeInTheDocument();
    });

    it("renders without data-testid when not provided", () => {
      render(<TextArea />);
      const textarea = screen.getByRole("textbox");
      expect(textarea.getAttribute("data-testid")).toBeNull();
    });
  });

  describe("CSS class styling", () => {
    it("renders as textarea element", () => {
      render(<TextArea />);
      expect(screen.getByRole("textbox")).toBeInTheDocument();
    });

    it("applies className prop", () => {
      render(<TextArea className="custom-textarea" />);
      const textarea = screen.getByRole("textbox");
      expect(textarea).toHaveClass("custom-textarea");
    });
  });

  describe("ARIA roles and attributes", () => {
    it("has textbox role", () => {
      render(<TextArea />);
      expect(screen.getByRole("textbox")).toBeInTheDocument();
    });

    it("forwards aria-label attribute", () => {
      render(<TextArea aria-label="Description" />);
      expect(screen.getByLabelText("Description")).toBeInTheDocument();
    });

    it("is not disabled by default", () => {
      render(<TextArea />);
      expect(screen.getByRole("textbox")).not.toBeDisabled();
    });

    it("is disabled when disabled prop is true", () => {
      render(<TextArea disabled />);
      expect(screen.getByRole("textbox")).toBeDisabled();
    });

    it("is readonly when readonly prop is true", () => {
      render(<TextArea readOnly />);
      expect(screen.getByRole("textbox")).toHaveAttribute("readonly");
    });
  });

  describe("HTML attributes", () => {
    it("forwards placeholder attribute", () => {
      render(<TextArea placeholder="Enter description..." />);
      expect(screen.getByPlaceholderText("Enter description...")).toBeInTheDocument();
    });

    it("forwards rows attribute", () => {
      render(<TextArea rows={5} />);
      expect(screen.getByRole("textbox")).toHaveAttribute("rows", "5");
    });

    it("forwards cols attribute", () => {
      render(<TextArea cols={40} />);
      expect(screen.getByRole("textbox")).toHaveAttribute("cols", "40");
    });

    it("forwards required attribute", () => {
      render(<TextArea required />);
      expect(screen.getByRole("textbox")).toHaveAttribute("required");
    });

    it("forwards id attribute", () => {
      render(<TextArea id="description-input" />);
      expect(screen.getByRole("textbox")).toHaveAttribute("id", "description-input");
    });

    it("forwards name attribute", () => {
      render(<TextArea name="description" />);
      expect(screen.getByRole("textbox")).toHaveAttribute("name", "description");
    });
  });
});

describe("Heimdall Select", () => {
  describe("data-testid attributes", () => {
    it("renders with data-testid when provided", () => {
      render(
        <Select data-testid="test-select">
          <option>Option</option>
        </Select>,
      );
      expect(screen.getByTestId("test-select")).toBeInTheDocument();
    });

    it("renders without data-testid when not provided", () => {
      render(
        <Select>
          <option>Option</option>
        </Select>,
      );
      const select = screen.getByRole("combobox");
      expect(select.getAttribute("data-testid")).toBeNull();
    });
  });

  describe("CSS class styling", () => {
    it("renders as select element", () => {
      render(
        <Select>
          <option>Option</option>
        </Select>,
      );
      expect(screen.getByRole("combobox")).toBeInTheDocument();
    });

    it("applies className prop", () => {
      render(
        <Select className="custom-select">
          <option>Option</option>
        </Select>,
      );
      const select = screen.getByRole("combobox");
      expect(select).toHaveClass("custom-select");
    });

    it("combines multiple className values", () => {
      render(
        <Select className="class1 class2">
          <option>Option</option>
        </Select>,
      );
      const select = screen.getByRole("combobox");
      expect(select).toHaveClass("class1");
      expect(select).toHaveClass("class2");
    });
  });

  describe("ARIA roles and attributes", () => {
    it("has combobox role", () => {
      render(
        <Select>
          <option>Option</option>
        </Select>,
      );
      expect(screen.getByRole("combobox")).toBeInTheDocument();
    });

    it("forwards aria-label attribute", () => {
      render(
        <Select aria-label="Choose option">
          <option>Option 1</option>
        </Select>,
      );
      expect(screen.getByLabelText("Choose option")).toBeInTheDocument();
    });

    it("forwards aria-describedby attribute", () => {
      render(
        <Select aria-describedby="help-text">
          <option>Option</option>
        </Select>,
      );
      expect(screen.getByRole("combobox")).toHaveAttribute("aria-describedby", "help-text");
    });

    it("is not disabled by default", () => {
      render(
        <Select>
          <option>Option</option>
        </Select>,
      );
      expect(screen.getByRole("combobox")).not.toBeDisabled();
    });

    it("is disabled when disabled prop is true", () => {
      render(
        <Select disabled>
          <option>Option</option>
        </Select>,
      );
      expect(screen.getByRole("combobox")).toBeDisabled();
    });
  });

  describe("options", () => {
    it("renders options from children", () => {
      render(
        <Select>
          <option value="1">Option 1</option>
          <option value="2">Option 2</option>
        </Select>,
      );
      expect(screen.getByText("Option 1")).toBeInTheDocument();
      expect(screen.getByText("Option 2")).toBeInTheDocument();
    });
  });

  describe("HTML attributes", () => {
    it("forwards required attribute", () => {
      render(
        <Select required>
          <option>Option</option>
        </Select>,
      );
      expect(screen.getByRole("combobox")).toHaveAttribute("required");
    });

    it("forwards id attribute", () => {
      render(
        <Select id="category-select">
          <option>Option</option>
        </Select>,
      );
      expect(screen.getByRole("combobox")).toHaveAttribute("id", "category-select");
    });

    it("forwards name attribute", () => {
      render(
        <Select name="category">
          <option>Option</option>
        </Select>,
      );
      expect(screen.getByRole("combobox")).toHaveAttribute("name", "category");
    });

    it("renders with listbox role when multiple is true", () => {
      render(
        <Select multiple>
          <option>Option</option>
        </Select>,
      );
      expect(screen.getByRole("listbox")).toHaveAttribute("multiple");
    });

    it("renders with listbox role when size is specified", () => {
      render(
        <Select size={5}>
          <option>Option</option>
        </Select>,
      );
      expect(screen.getByRole("listbox")).toHaveAttribute("size", "5");
    });
  });
});
