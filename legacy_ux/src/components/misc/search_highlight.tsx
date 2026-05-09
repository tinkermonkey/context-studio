import React from "react";

interface SearchHighlightProps {
  content?: string;
  searchText?: string;
}

const SearchHighlight: React.FC<SearchHighlightProps> = ({
  content = "",
  searchText = "",
}) => {
  if (!searchText || !content) return <>{content}</>;

  // Split content by searchText, keeping matches
  const parts = content.split(new RegExp(`(${searchText})`, "gi"));

  return (
    <>
      {parts.map((part, idx) =>
        part.toLowerCase() === searchText.toLowerCase() ? (
          <span key={idx} className="rounded bg-yellow-200 px-0.5">
            {part}
          </span>
        ) : (
          <React.Fragment key={idx}>{part}</React.Fragment>
        ),
      )}
    </>
  );
};

export default SearchHighlight;
