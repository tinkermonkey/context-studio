import { describe, it, expect, vi } from "vitest";
import { screen, waitFor, fireEvent, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { render } from "@/test/test-utils";
import { EditableField } from "../EditableField";

describe("EditableField", () => {
  describe("view mode", () => {
    it("renders label", () => {
      render(<EditableField label="Name" value="Alice" onSave={vi.fn()} />);
      expect(screen.getByText("Name")).toBeInTheDocument();
    });

    it("renders value in view mode", () => {
      render(
        <EditableField label="Name" value="Alice" onSave={vi.fn()} data-testid="name-field" />,
      );
      expect(screen.getByTestId("name-field-view")).toHaveTextContent("Alice");
    });

    it("shows placeholder when value is empty", () => {
      render(
        <EditableField
          label="Name"
          value=""
          onSave={vi.fn()}
          placeholder="Enter name"
          data-testid="name-field"
        />,
      );
      expect(screen.getByTestId("name-field-view")).toHaveTextContent("Enter name");
    });

    it("shows em-dash when value is empty and no placeholder provided", () => {
      render(
        <EditableField label="Name" value="" onSave={vi.fn()} data-testid="name-field" />,
      );
      expect(screen.getByTestId("name-field-view")).toHaveTextContent("—");
    });

    it("applies data-testid to root element", () => {
      const { container } = render(
        <EditableField label="Name" value="Alice" onSave={vi.fn()} data-testid="name-field" />,
      );
      expect(container.querySelector('[data-testid="name-field"]')).toHaveClass("editable-field");
    });

    it("view element has button role when not disabled", () => {
      render(<EditableField label="Name" value="Alice" onSave={vi.fn()} />);
      expect(screen.getByRole("button", { name: "Edit Name" })).toBeInTheDocument();
    });

    it("view element has no role when disabled", () => {
      const { container } = render(
        <EditableField
          label="Name"
          value="Alice"
          onSave={vi.fn()}
          disabled
          data-testid="name-field"
        />,
      );
      const viewEl = container.querySelector('[data-testid="name-field-view"]');
      expect(viewEl).not.toHaveAttribute("role");
    });

    it("applies disabled CSS class when disabled", () => {
      const { container } = render(
        <EditableField
          label="Name"
          value="Alice"
          onSave={vi.fn()}
          disabled
          data-testid="name-field"
        />,
      );
      expect(container.querySelector(".editable-field__view--disabled")).toBeInTheDocument();
    });

    it("shows select option label in view mode", () => {
      render(
        <EditableField
          label="Status"
          value="active"
          onSave={vi.fn()}
          kind="Select"
          options={[
            { value: "active", label: "Active" },
            { value: "inactive", label: "Inactive" },
          ]}
          data-testid="status-field"
        />,
      );
      expect(screen.getByTestId("status-field-view")).toHaveTextContent("Active");
    });

    it("shows raw value when select value has no matching option", () => {
      render(
        <EditableField
          label="Status"
          value="unknown"
          onSave={vi.fn()}
          kind="Select"
          options={[{ value: "active", label: "Active" }]}
          data-testid="status-field"
        />,
      );
      expect(screen.getByTestId("status-field-view")).toHaveTextContent("unknown");
    });
  });

  describe("entering edit mode", () => {
    it("enters edit mode when view is clicked", async () => {
      const user = userEvent.setup();
      render(
        <EditableField label="Name" value="Alice" onSave={vi.fn()} data-testid="name-field" />,
      );
      await user.click(screen.getByTestId("name-field-view"));
      expect(screen.getByTestId("name-field-input")).toBeInTheDocument();
    });

    it("enters edit mode when Enter key is pressed on view element", () => {
      render(
        <EditableField label="Name" value="Alice" onSave={vi.fn()} data-testid="name-field" />,
      );
      fireEvent.keyDown(screen.getByTestId("name-field-view"), { key: "Enter" });
      expect(screen.getByTestId("name-field-input")).toBeInTheDocument();
    });

    it("does not enter edit mode when disabled", async () => {
      const user = userEvent.setup();
      const { container } = render(
        <EditableField
          label="Name"
          value="Alice"
          onSave={vi.fn()}
          disabled
          data-testid="name-field"
        />,
      );
      await user.click(container.querySelector('[data-testid="name-field-view"]')!);
      expect(screen.queryByTestId("name-field-input")).not.toBeInTheDocument();
    });

    it("initializes edit value to current value on edit mode entry", async () => {
      const user = userEvent.setup();
      render(
        <EditableField label="Name" value="Alice" onSave={vi.fn()} data-testid="name-field" />,
      );
      await user.click(screen.getByTestId("name-field-view"));
      expect(screen.getByTestId("name-field-input")).toHaveValue("Alice");
    });
  });

  describe("field kind rendering", () => {
    it("renders TextInput (default) as text input in edit mode", async () => {
      const user = userEvent.setup();
      render(
        <EditableField label="Name" value="Alice" onSave={vi.fn()} data-testid="name-field" />,
      );
      await user.click(screen.getByTestId("name-field-view"));
      const input = screen.getByTestId("name-field-input");
      expect(input).toBeInTheDocument();
      expect(input).toHaveAttribute("type", "text");
    });

    it("renders TextArea as textarea element in edit mode", async () => {
      const user = userEvent.setup();
      render(
        <EditableField
          label="Notes"
          value="text"
          onSave={vi.fn()}
          kind="TextArea"
          data-testid="notes-field"
        />,
      );
      await user.click(screen.getByTestId("notes-field-view"));
      const input = screen.getByTestId("notes-field-input");
      expect(input.tagName.toLowerCase()).toBe("textarea");
    });

    it("renders NumberInput as number input in edit mode", async () => {
      const user = userEvent.setup();
      render(
        <EditableField
          label="Count"
          value="5"
          onSave={vi.fn()}
          kind="NumberInput"
          data-testid="count-field"
        />,
      );
      await user.click(screen.getByTestId("count-field-view"));
      const input = screen.getByTestId("count-field-input");
      expect(input).toHaveAttribute("type", "number");
    });

    it("renders Select with options in edit mode", async () => {
      const user = userEvent.setup();
      render(
        <EditableField
          label="Status"
          value="active"
          onSave={vi.fn()}
          kind="Select"
          options={[
            { value: "active", label: "Active" },
            { value: "inactive", label: "Inactive" },
          ]}
          data-testid="status-field"
        />,
      );
      await user.click(screen.getByTestId("status-field-view"));
      expect(screen.getByRole("combobox")).toBeInTheDocument();
      expect(screen.getByText("Active")).toBeInTheDocument();
      expect(screen.getByText("Inactive")).toBeInTheDocument();
    });
  });

  describe("save on blur", () => {
    it("calls onSave with trimmed value when field loses focus", async () => {
      const onSave = vi.fn().mockResolvedValue(undefined);
      const user = userEvent.setup();
      render(
        <EditableField
          label="Name"
          value="Alice"
          onSave={onSave}
          data-testid="name-field"
        />,
      );
      await user.click(screen.getByTestId("name-field-view"));
      const input = screen.getByTestId("name-field-input");
      await user.clear(input);
      await user.type(input, "  Bob  ");
      fireEvent.blur(input);
      await waitFor(() => {
        expect(onSave).toHaveBeenCalledWith("Bob");
      });
    });

    it("does not call onSave when value is unchanged after blur", async () => {
      const onSave = vi.fn();
      const user = userEvent.setup();
      render(
        <EditableField
          label="Name"
          value="Alice"
          onSave={onSave}
          data-testid="name-field"
        />,
      );
      await user.click(screen.getByTestId("name-field-view"));
      fireEvent.blur(screen.getByTestId("name-field-input"));
      await waitFor(() => {
        expect(screen.queryByTestId("name-field-input")).not.toBeInTheDocument();
      });
      expect(onSave).not.toHaveBeenCalled();
    });

    it("exits edit mode after blur", async () => {
      const user = userEvent.setup();
      render(
        <EditableField label="Name" value="Alice" onSave={vi.fn()} data-testid="name-field" />,
      );
      await user.click(screen.getByTestId("name-field-view"));
      fireEvent.blur(screen.getByTestId("name-field-input"));
      await waitFor(() => {
        expect(screen.queryByTestId("name-field-input")).not.toBeInTheDocument();
      });
    });
  });

  describe("validation", () => {
    it("shows validation error on blur when validate returns a message", async () => {
      const user = userEvent.setup();
      render(
        <EditableField
          label="Name"
          value=""
          onSave={vi.fn()}
          validate={(v) => (!v.trim() ? "Required" : undefined)}
          data-testid="name-field"
        />,
      );
      await user.click(screen.getByTestId("name-field-view"));
      fireEvent.blur(screen.getByTestId("name-field-input"));
      await waitFor(() => {
        expect(screen.getByRole("alert")).toHaveTextContent("Required");
      });
    });

    it("stays in edit mode when validation fails on blur", async () => {
      const user = userEvent.setup();
      render(
        <EditableField
          label="Name"
          value=""
          onSave={vi.fn()}
          validate={(v) => (!v.trim() ? "Required" : undefined)}
          data-testid="name-field"
        />,
      );
      await user.click(screen.getByTestId("name-field-view"));
      fireEvent.blur(screen.getByTestId("name-field-input"));
      await waitFor(() => {
        expect(screen.getByTestId("name-field-input")).toBeInTheDocument();
      });
    });

    it("does not call onSave when validation fails", async () => {
      const onSave = vi.fn();
      const user = userEvent.setup();
      render(
        <EditableField
          label="Name"
          value=""
          onSave={onSave}
          validate={(v) => (!v.trim() ? "Required" : undefined)}
          data-testid="name-field"
        />,
      );
      await user.click(screen.getByTestId("name-field-view"));
      fireEvent.blur(screen.getByTestId("name-field-input"));
      await waitFor(() => {
        expect(screen.getByRole("alert")).toBeInTheDocument();
      });
      expect(onSave).not.toHaveBeenCalled();
    });

    it("clears validation error when user types a valid value", async () => {
      const user = userEvent.setup();
      render(
        <EditableField
          label="Name"
          value=""
          onSave={vi.fn()}
          validate={(v) => (!v.trim() ? "Required" : undefined)}
          data-testid="name-field"
        />,
      );
      await user.click(screen.getByTestId("name-field-view"));
      fireEvent.blur(screen.getByTestId("name-field-input"));
      await waitFor(() => {
        expect(screen.getByRole("alert")).toBeInTheDocument();
      });
      await user.type(screen.getByTestId("name-field-input"), "Alice");
      await waitFor(() => {
        expect(screen.queryByRole("alert")).not.toBeInTheDocument();
      });
    });
  });

  describe("save status", () => {
    it("shows Saved indicator after successful save", async () => {
      const onSave = vi.fn().mockResolvedValue(undefined);
      render(
        <EditableField
          label="Name"
          value="Alice"
          onSave={onSave}
          data-testid="name-field"
        />,
      );
      fireEvent.click(screen.getByTestId("name-field-view"));
      fireEvent.change(screen.getByTestId("name-field-input"), { target: { value: "Bob" } });
      fireEvent.blur(screen.getByTestId("name-field-input"));
      await waitFor(() => {
        expect(screen.getByTestId("name-field-saved")).toBeInTheDocument();
      });
    });

    it("auto-clears Saved indicator after 1600ms", async () => {
      let clearSavedCallback: (() => void) | undefined;
      const origSetTimeout = global.setTimeout;
      vi.spyOn(global, "setTimeout").mockImplementation((fn: any, delay: any, ...args: any[]) => {
        if (delay === 1600) {
          clearSavedCallback = fn;
          return 0 as any;
        }
        return origSetTimeout(fn, delay, ...args) as any;
      });

      try {
        const onSave = vi.fn().mockResolvedValue(undefined);
        render(
          <EditableField
            label="Name"
            value="Alice"
            onSave={onSave}
            data-testid="name-field"
          />,
        );
        fireEvent.click(screen.getByTestId("name-field-view"));
        fireEvent.change(screen.getByTestId("name-field-input"), { target: { value: "Bob" } });
        fireEvent.blur(screen.getByTestId("name-field-input"));
        await waitFor(() => {
          expect(screen.getByTestId("name-field-saved")).toBeInTheDocument();
        });
        expect(clearSavedCallback).toBeDefined();
        act(() => clearSavedCallback!());
        expect(screen.queryByTestId("name-field-saved")).not.toBeInTheDocument();
      } finally {
        vi.restoreAllMocks();
      }
    });

    it("shows error message and re-enters edit mode when save fails", async () => {
      const onSave = vi.fn().mockRejectedValue(new Error("Network error"));
      render(
        <EditableField
          label="Name"
          value="Alice"
          onSave={onSave}
          data-testid="name-field"
        />,
      );
      fireEvent.click(screen.getByTestId("name-field-view"));
      fireEvent.change(screen.getByTestId("name-field-input"), { target: { value: "Bob" } });
      fireEvent.blur(screen.getByTestId("name-field-input"));
      await waitFor(() => {
        expect(screen.getByText("Network error")).toBeInTheDocument();
        expect(screen.getByTestId("name-field-input")).toBeInTheDocument();
      });
    });
  });

  describe("Escape key", () => {
    it("exits edit mode on Escape", async () => {
      const user = userEvent.setup();
      render(
        <EditableField label="Name" value="Alice" onSave={vi.fn()} data-testid="name-field" />,
      );
      await user.click(screen.getByTestId("name-field-view"));
      fireEvent.keyDown(screen.getByTestId("name-field-input"), { key: "Escape" });
      expect(screen.queryByTestId("name-field-input")).not.toBeInTheDocument();
    });

    it("restores the original value on Escape", async () => {
      const user = userEvent.setup();
      render(
        <EditableField label="Name" value="Alice" onSave={vi.fn()} data-testid="name-field" />,
      );
      await user.click(screen.getByTestId("name-field-view"));
      await user.clear(screen.getByTestId("name-field-input"));
      await user.type(screen.getByTestId("name-field-input"), "Bob");
      fireEvent.keyDown(screen.getByTestId("name-field-input"), { key: "Escape" });
      expect(screen.getByTestId("name-field-view")).toHaveTextContent("Alice");
    });

    it("clears validation error on Escape", async () => {
      const user = userEvent.setup();
      render(
        <EditableField
          label="Name"
          value=""
          onSave={vi.fn()}
          validate={(v) => (!v.trim() ? "Required" : undefined)}
          data-testid="name-field"
        />,
      );
      await user.click(screen.getByTestId("name-field-view"));
      fireEvent.blur(screen.getByTestId("name-field-input"));
      await waitFor(() => {
        expect(screen.getByRole("alert")).toBeInTheDocument();
      });
      fireEvent.keyDown(screen.getByTestId("name-field-input"), { key: "Escape" });
      expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    });
  });

  describe("Enter key behavior", () => {
    it("triggers save on Enter for TextInput", async () => {
      const onSave = vi.fn().mockResolvedValue(undefined);
      const user = userEvent.setup();
      render(
        <EditableField label="Name" value="Alice" onSave={onSave} data-testid="name-field" />,
      );
      await user.click(screen.getByTestId("name-field-view"));
      await user.clear(screen.getByTestId("name-field-input"));
      await user.type(screen.getByTestId("name-field-input"), "Bob");
      fireEvent.keyDown(screen.getByTestId("name-field-input"), { key: "Enter" });
      await waitFor(() => {
        expect(onSave).toHaveBeenCalledWith("Bob");
      });
    });

    it("does not trigger save on Enter for TextArea", async () => {
      const onSave = vi.fn();
      const user = userEvent.setup();
      render(
        <EditableField
          label="Notes"
          value="text"
          onSave={onSave}
          kind="TextArea"
          data-testid="notes-field"
        />,
      );
      await user.click(screen.getByTestId("notes-field-view"));
      await user.clear(screen.getByTestId("notes-field-input"));
      await user.type(screen.getByTestId("notes-field-input"), "updated text");
      fireEvent.keyDown(screen.getByTestId("notes-field-input"), { key: "Enter" });
      expect(screen.getByTestId("notes-field-input")).toBeInTheDocument();
      expect(onSave).not.toHaveBeenCalled();
    });
  });

  describe("Select change behavior", () => {
    it("exits edit mode immediately when select changes without requiring blur", async () => {
      const user = userEvent.setup();
      render(
        <EditableField
          label="Status"
          value="active"
          onSave={vi.fn().mockResolvedValue(undefined)}
          kind="Select"
          options={[
            { value: "active", label: "Active" },
            { value: "inactive", label: "Inactive" },
          ]}
          data-testid="status-field"
        />,
      );
      await user.click(screen.getByTestId("status-field-view"));
      expect(screen.getByRole("combobox")).toBeInTheDocument();
      fireEvent.change(screen.getByRole("combobox"), { target: { value: "inactive" } });
      await waitFor(() => {
        expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
      });
    });

    it("calls onSave when select value changes", async () => {
      const onSave = vi.fn().mockResolvedValue(undefined);
      const user = userEvent.setup();
      render(
        <EditableField
          label="Status"
          value="active"
          onSave={onSave}
          kind="Select"
          options={[
            { value: "active", label: "Active" },
            { value: "inactive", label: "Inactive" },
          ]}
          data-testid="status-field"
        />,
      );
      await user.click(screen.getByTestId("status-field-view"));
      fireEvent.change(screen.getByRole("combobox"), { target: { value: "inactive" } });
      await waitFor(() => {
        expect(onSave).toHaveBeenCalledWith("inactive");
      });
    });
  });
});
