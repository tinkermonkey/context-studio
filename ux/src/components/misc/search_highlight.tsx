
import React from "react";
import { Badge } from "flowbite-react";

interface SearchHighlightProps {
  content?: string;
  searchText?: string;
}

const SearchHighlight: React.FC<SearchHighlightProps> = ({ content = "", searchText = "" }) => {
  if (!searchText || !content) return <>{content}</>;

  // Split content by searchText, keeping matches
  const parts = content.split(new RegExp(`(${searchText})`, "gi"));

  return (
    <>
      {parts.map((part, idx) =>
        part.toLowerCase() === searchText.toLowerCase() ? (
          <Badge color="info" key={idx} className="inline px-0">{part}</Badge>
        ) : (
          <React.Fragment key={idx}>{part}</React.Fragment>
        )
      )}
    </>
  );
};

export default SearchHighlight;
