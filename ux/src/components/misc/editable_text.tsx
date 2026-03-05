import React, { useRef, useState } from "react";
import ContentEditable from "react-contenteditable";

type EditableTextProps = {
  children: React.ReactNode;
  tagName?: string;
  disabled?: boolean;
  className?: string;
  onChange?: (value: string) => void;
};

const EditableText: React.FC<EditableTextProps> = ({
  children,
  tagName = "span",
  disabled = false,
  className = "",
  onChange,
}) => {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const contentEditable = useRef<any>(null);
  const [html, setHtml] = useState(
    typeof children === "string"
      ? children
      : React.Children.map(children, (child) =>
          typeof child === "string" ? child : "",
        )?.join("") || "",
  );

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const handleChange = (evt: React.ChangeEvent<any>) => {
    setHtml(evt.target.value);
    if (onChange) onChange(evt.target.value);
  };

  return (
    <ContentEditable
      innerRef={contentEditable}
      html={html}
      disabled={disabled}
      onChange={handleChange}
      tagName={tagName}
      className={className}
    />
  );
};

export { EditableText };
