"use client";
 
import React from "react";
 
// ---------------------------------------------------------------------------
// Lightweight Markdown renderer for Azure OpenAI GPT-4 RAG chatbot output.
// Pure React/CSS — no external libraries. Handles bold, italic, inline code,
// fenced code blocks, bullet/numbered lists (with nesting), headings (h3/h4),
// blockquotes, citation references [N], horizontal rules, and a distinct
// "Sources:" section.
// ---------------------------------------------------------------------------
 
/* ---- inline style helpers ------------------------------------------------ */
 
const styles = {
  wrapper: {
    fontSize: "var(--font-size-sm)",
    color: "var(--color-text-primary)",
    lineHeight: 1.65,
    wordBreak: "break-word" as const,
  },
 
  h3: {
    fontSize: "var(--font-size-lg)",
    fontWeight: 600,
    margin: "var(--spacing-md) 0 var(--spacing-sm)",
    color: "var(--color-text-primary)",
    lineHeight: 1.35,
  },
  h4: {
    fontSize: "var(--font-size-sm)",
    fontWeight: 600,
    margin: "var(--spacing-sm) 0 var(--spacing-xs)",
    color: "var(--color-text-primary)",
    lineHeight: 1.4,
  },
 
  paragraph: {
    margin: "0 0 var(--spacing-sm)",
  },
 
  blockquote: {
    borderLeft: "3px solid var(--color-accent)",
    paddingLeft: "var(--spacing-md)",
    margin: "var(--spacing-sm) 0",
    color: "var(--color-text-secondary)",
    fontStyle: "italic" as const,
  },
 
  codeBlock: {
    display: "block" as const,
    background: "#1e1e2e",
    color: "#cdd6f4",
    fontFamily: "var(--font-mono)",
    fontSize: "var(--font-size-xs)",
    borderRadius: "var(--radius-sm)",
    padding: "var(--spacing-sm) var(--spacing-md)",
    margin: "var(--spacing-sm) 0",
    overflowX: "auto" as const,
    whiteSpace: "pre" as const,
    lineHeight: 1.55,
  },
 
  inlineCode: {
    fontFamily: "var(--font-mono)",
    fontSize: "0.85em",
    background: "var(--color-bg-secondary)",
    border: "1px solid var(--color-border)",
    borderRadius: "var(--radius-xs)",
    padding: "1px 5px",
  },
 
  hr: {
    border: "none",
    borderTop: "1px solid var(--color-border)",
    margin: "var(--spacing-md) 0",
  },
 
  ul: {
    margin: "var(--spacing-xs) 0 var(--spacing-sm)",
    paddingLeft: "var(--spacing-lg)",
    listStyleType: "disc" as const,
  },
  ol: {
    margin: "var(--spacing-xs) 0 var(--spacing-sm)",
    paddingLeft: "var(--spacing-lg)",
    listStyleType: "decimal" as const,
  },
  li: {
    margin: "2px 0",
  },
 
  citation: {
    display: "inline-block" as const,
    fontSize: "var(--font-size-2xs)",
    fontWeight: 600,
    lineHeight: 1,
    color: "var(--color-accent)",
    background: "var(--color-accent-light)",
    borderRadius: "var(--radius-xs)",
    padding: "1px 4px",
    verticalAlign: "super" as const,
    marginLeft: "1px",
    marginRight: "1px",
    cursor: "default",
  },
 
  sources: {
    marginTop: "var(--spacing-md)",
    paddingTop: "var(--spacing-sm)",
    borderTop: "1px solid var(--color-border)",
    fontSize: "var(--font-size-xs)",
    color: "var(--color-text-muted)",
    lineHeight: 1.55,
  },
} as const;
 
/* ---- inline‑level parser ------------------------------------------------ */
 
/**
 * Parse inline markdown tokens into React nodes.
 * Handles: **bold**, *italic*, `code`, and [N] citation refs.
 */
function parseInline(text: string, keyPrefix: string): React.ReactNode[] {
  const nodes: React.ReactNode[] = [];
  // Regex covers: **bold**, *italic*, `code`, [number] citations
  const inlineRe =
    /(\*\*(.+?)\*\*)|(\*(.+?)\*)|(`([^`]+?)`)|(\[(\d+)\])/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  let i = 0;
 
  while ((match = inlineRe.exec(text)) !== null) {
    // Push plain text before this match
    if (match.index > lastIndex) {
      nodes.push(text.slice(lastIndex, match.index));
    }
 
    if (match[1]) {
      // **bold**
      nodes.push(
        <strong key={`${keyPrefix}-b${i}`}>{match[2]}</strong>
      );
    } else if (match[3]) {
      // *italic*
      nodes.push(<em key={`${keyPrefix}-i${i}`}>{match[4]}</em>);
    } else if (match[5]) {
      // `inline code`
      nodes.push(
        <code key={`${keyPrefix}-c${i}`} style={styles.inlineCode}>
          {match[6]}
        </code>
      );
    } else if (match[7]) {
      // [N] citation
      nodes.push(
        <span key={`${keyPrefix}-ref${i}`} style={styles.citation} title={`Citation ${match[8]}`}>
          {match[8]}
        </span>
      );
    }
 
    lastIndex = match.index + match[0].length;
    i++;
  }
 
  // Trailing plain text
  if (lastIndex < text.length) {
    nodes.push(text.slice(lastIndex));
  }
 
  return nodes;
}
 
/* ---- list builder ------------------------------------------------------- */
 
interface ListItem {
  indent: number;
  ordered: boolean;
  content: string;
}
 
function buildListTree(
  items: ListItem[],
  keyPrefix: string,
): React.ReactNode {
  if (items.length === 0) return null;
 
  const result: React.ReactNode[] = [];
  let i = 0;
 
  while (i < items.length) {
    const item = items[i];
    // Collect children (items at a deeper indent level immediately following)
    const children: ListItem[] = [];
    let j = i + 1;
    while (j < items.length && items[j].indent > item.indent) {
      children.push(items[j]);
      j++;
    }
 
    result.push(
      <li key={`${keyPrefix}-li${i}`} style={styles.li}>
        {parseInline(item.content, `${keyPrefix}-li${i}`)}
        {children.length > 0 && buildListTree(children, `${keyPrefix}-li${i}-sub`)}
      </li>
    );
 
    i = j;
  }
 
  const ordered = items[0].ordered;
  const Tag = ordered ? "ol" : "ul";
  return (
    <Tag key={keyPrefix} style={ordered ? styles.ol : styles.ul}>
      {result}
    </Tag>
  );
}
 
/* ---- block‑level parser ------------------------------------------------- */
 
export default function MarkdownRenderer({
  content,
}: {
  content: string;
}) {
  if (!content) return null;
 
  let safeContent: string;
  try {
    safeContent = typeof content === "string" ? content : String(content);
  } catch {
    return null;
  }
 
  const elements: React.ReactNode[] = [];
  const lines = safeContent.split("\n");
  let i = 0;
  let key = 0;
  let inSources = false;
 
  while (i < lines.length) {
    const line = lines[i];
 
    // --- fenced code block ---
    if (line.trimStart().startsWith("```")) {
      const codeLines: string[] = [];
      i++; // skip opening fence
      while (i < lines.length && !lines[i].trimStart().startsWith("```")) {
        codeLines.push(lines[i]);
        i++;
      }
      i++; // skip closing fence (or end of input)
      elements.push(
        <pre key={key++} style={styles.codeBlock}>
          <code>{codeLines.join("\n")}</code>
        </pre>
      );
      continue;
    }
 
    // --- horizontal rule ---
    if (/^---+\s*$/.test(line.trim())) {
      elements.push(<hr key={key++} style={styles.hr} />);
      i++;
      continue;
    }
 
    // --- headings ---
    const headingMatch = line.match(/^(#{1,4})\s+(.+)/);
    if (headingMatch) {
      const level = headingMatch[1].length;
      const text = headingMatch[2];
      const Tag = level <= 3 ? "h3" : "h4";
      const tagStyle = level <= 3 ? styles.h3 : styles.h4;
      elements.push(
        <Tag key={key++} style={tagStyle}>
          {parseInline(text, `h-${key}`)}
        </Tag>
      );
      i++;
      continue;
    }
 
    // --- blockquote ---
    if (line.startsWith("> ")) {
      const quoteLines: string[] = [];
      while (i < lines.length && lines[i].startsWith("> ")) {
        quoteLines.push(lines[i].slice(2));
        i++;
      }
      elements.push(
        <blockquote key={key++} style={styles.blockquote}>
          {quoteLines.map((ql, qi) => (
            <React.Fragment key={qi}>
              {qi > 0 && <br />}
              {parseInline(ql, `bq-${key}-${qi}`)}
            </React.Fragment>
          ))}
        </blockquote>
      );
      continue;
    }
 
    // --- bullet list ---
    const bulletMatch = line.match(/^(\s*)[-*]\s+(.+)/);
    if (bulletMatch) {
      const listItems: ListItem[] = [];
      while (i < lines.length) {
        const m = lines[i].match(/^(\s*)[-*]\s+(.+)/);
        if (!m) break;
        listItems.push({
          indent: m[1].length,
          ordered: false,
          content: m[2],
        });
        i++;
      }
      elements.push(
        <React.Fragment key={key++}>
          {buildListTree(listItems, `ul-${key}`)}
        </React.Fragment>
      );
      continue;
    }
 
    // --- numbered list ---
    const olMatch = line.match(/^(\s*)\d+[.)]\s+(.+)/);
    if (olMatch) {
      const listItems: ListItem[] = [];
      while (i < lines.length) {
        const m = lines[i].match(/^(\s*)\d+[.)]\s+(.+)/);
        if (!m) break;
        listItems.push({
          indent: m[1].length,
          ordered: true,
          content: m[2],
        });
        i++;
      }
      elements.push(
        <React.Fragment key={key++}>
          {buildListTree(listItems, `ol-${key}`)}
        </React.Fragment>
      );
      continue;
    }
 
    // --- "Sources:" section detection ---
    if (/^sources?\s*:/i.test(line.trim())) {
      inSources = true;
      const sourceLines: string[] = [];
      // Include the current "Sources:" line and everything after it
      while (i < lines.length) {
        sourceLines.push(lines[i]);
        i++;
      }
      elements.push(
        <div key={key++} style={styles.sources}>
          {sourceLines.map((sl, si) => (
            <React.Fragment key={si}>
              {si > 0 && <br />}
              {parseInline(sl, `src-${key}-${si}`)}
            </React.Fragment>
          ))}
        </div>
      );
      continue;
    }
 
    // --- blank line ---
    if (line.trim() === "") {
      i++;
      continue;
    }
 
    // --- plain paragraph (may span consecutive non-blank lines) ---
    {
      const paraLines: string[] = [];
      while (
        i < lines.length &&
        lines[i].trim() !== "" &&
        !lines[i].trimStart().startsWith("```") &&
        !/^---+\s*$/.test(lines[i].trim()) &&
        !lines[i].match(/^#{3,4}\s+/) &&
        !lines[i].startsWith("> ") &&
        !lines[i].match(/^\s*[-*]\s+/) &&
        !lines[i].match(/^\s*\d+[.)]\s+/) &&
        !/^sources?\s*:/i.test(lines[i].trim())
      ) {
        paraLines.push(lines[i]);
        i++;
      }
 
      if (paraLines.length > 0) {
        elements.push(
          <p key={key++} style={styles.paragraph}>
            {paraLines.map((pl, pi) => (
              <React.Fragment key={pi}>
                {pi > 0 && <br />}
                {parseInline(pl, `p-${key}-${pi}`)}
              </React.Fragment>
            ))}
          </p>
        );
      } else {
        // Safety: advance to avoid infinite loop on unexpected input
        i++;
      }
    }
  }
 
  return <div style={styles.wrapper}>{elements}</div>;
}
 