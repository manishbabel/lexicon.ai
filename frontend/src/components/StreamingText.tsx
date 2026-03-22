import type { ReactNode } from "react";

/**
 * Renders text with **bold** markdown parsed and a blinking cursor while streaming.
 */

function parseMarkdownBold(text: string): ReactNode[] {
  const parts: ReactNode[] = [];
  const regex = /\*\*(.+?)\*\*/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }
    parts.push(
      <strong key={match.index} className="font-semibold text-text">
        {match[1]}
      </strong>,
    );
    lastIndex = match.index + match[0].length;
  }

  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }

  return parts;
}

export default function StreamingText({
  text,
  streaming,
  className = "",
}: {
  text: string;
  streaming: boolean;
  className?: string;
}) {
  return (
    <span className={className}>
      {parseMarkdownBold(text)}
      {streaming && (
        <span className="inline-block w-0.5 h-[1em] bg-accent ml-0.5 animate-pulse align-text-bottom" />
      )}
    </span>
  );
}
