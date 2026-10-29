import { type MouseEvent, type ReactNode } from "react";
import Markdown, { defaultUrlTransform, type Components } from "react-markdown";
import { useNavigate } from "@tanstack/react-router";
import { linkPath } from "@/lib/entityPaths";
import { resolveEntityLink, type KnownEntities } from "./chatModel";

interface ChatAnswerProps {
  text: string;
  known: KnownEntities;
}

/** Keep `entity:` hrefs for the link renderer; sanitize everything else as usual. */
function urlTransform(url: string): string {
  return url.startsWith("entity:") ? url : defaultUrlTransform(url);
}

/**
 * Markdown answer text. `[Title](entity:<kind>/<id>)` links become entity-page
 * (or proposal review page) links only when the id came from this
 * conversation's tool results or page context; others (unknown ids, property links, which have no page) render as
 * plain text. Clicking navigates the page; the panel stays open.
 */
export function ChatAnswer({ text, known }: ChatAnswerProps) {
  const navigate = useNavigate();

  const components: Components = {
    a: ({ href, children }) => {
      if (href?.startsWith("entity:")) {
        const target = resolveEntityLink(href, known);
        if (!target) {
          return <span data-testid="chat-entity-text">{children as ReactNode}</span>;
        }
        const path = linkPath(target.kind, target.id);
        const onClick = (event: MouseEvent<HTMLAnchorElement>) => {
          if (event.metaKey || event.ctrlKey || event.shiftKey || event.button !== 0) return;
          event.preventDefault();
          navigate({ to: path });
        };
        return (
          <a
            href={path}
            onClick={onClick}
            className="chat-entity-link"
            data-testid="chat-entity-link"
            data-entity-kind={target.kind}
            data-entity-id={target.id}
          >
            {children}
          </a>
        );
      }
      return (
        <a href={href} target="_blank" rel="noreferrer noopener">
          {children}
        </a>
      );
    },
  };

  return (
    <div className="chat-answer" data-testid="chat-answer">
      <Markdown components={components} urlTransform={urlTransform}>
        {text}
      </Markdown>
    </div>
  );
}
