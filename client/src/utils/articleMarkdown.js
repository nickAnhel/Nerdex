const DIRECTIVE_LINE_RE = /^::([a-z_]+)\{(.*)\}\s*$/;
const SPOILER_OPEN_RE = /^:::spoiler(?:\[([^\]]*)\])?\s*$/;
const ATTRIBUTE_RE = /([a-z][a-z0-9_-]*)="([^"]*)"/g;
const MERMAID_BLOCK_RE = /```mermaid\s*\n([\s\S]*?)```/g;
const LEADING_MARKDOWN_RE = /^(?:>\s*|[-*+]\s+|\d+\.\s+|\[[ xX]\]\s+)+/;
const IMAGE_LINK_RE = /!\[([^\]]*)\]\([^)]+\)/g;
const MARKDOWN_LINK_RE = /\[([^\]]+)\]\([^)]+\)/g;
const INLINE_FORMATTING_RE = /(`+|[*_~]+)/g;


export function slugifyHeading(value) {
    return (value || "")
        .trim()
        .toLowerCase()
        .replace(/[^a-zа-яё0-9]+/g, "-")
        .replace(/^-+|-+$/g, "");
}

export function buildArticleAssetLookup(article, extraAssets = []) {
    const lookup = {};
    const allAssets = [
        ...(article?.referenced_assets || []),
        ...(article?.cover ? [article.cover] : []),
        ...(extraAssets || []),
    ];

    allAssets.forEach((asset) => {
        if (asset?.asset_id) {
            lookup[asset.asset_id] = asset;
        }
    });

    return lookup;
}

export function parseArticleMarkdown(bodyMarkdown) {
    const lines = (bodyMarkdown || "").split("\n");
    const blocks = [];
    let markdownBuffer = [];
    let currentSpoiler = null;
    let inCodeBlock = false;
    let mermaidBuffer = null;

    const flushMarkdown = () => {
        if (markdownBuffer.length === 0) {
            return;
        }

        blocks.push({
            type: "markdown",
            content: markdownBuffer.join("\n"),
        });
        markdownBuffer = [];
    };

    lines.forEach((line) => {
        const trimmed = line.trim();

        if (!currentSpoiler && trimmed.startsWith("```mermaid")) {
            flushMarkdown();
            mermaidBuffer = [];
            return;
        }

        if (mermaidBuffer !== null) {
            if (trimmed === "```") {
                blocks.push({
                    type: "mermaid",
                    code: mermaidBuffer.join("\n"),
                });
                mermaidBuffer = null;
                return;
            }

            mermaidBuffer.push(line);
            return;
        }

        if (trimmed.startsWith("```")) {
            inCodeBlock = !inCodeBlock;
            if (currentSpoiler) {
                currentSpoiler.body.push(line);
            } else {
                markdownBuffer.push(line);
            }
            return;
        }

        if (!inCodeBlock && !currentSpoiler) {
            const spoilerMatch = trimmed.match(SPOILER_OPEN_RE);
            if (spoilerMatch) {
                flushMarkdown();
                currentSpoiler = {
                    title: spoilerMatch[1] || "Spoiler",
                    body: [],
                };
                return;
            }

            const directiveMatch = trimmed.match(DIRECTIVE_LINE_RE);
            if (directiveMatch) {
                flushMarkdown();
                const attrs = parseDirectiveAttributes(directiveMatch[2]);
                blocks.push({
                    type: directiveMatch[1],
                    attrs,
                });
                return;
            }
        } else if (!inCodeBlock && currentSpoiler && trimmed === ":::") {
            blocks.push({
                type: "spoiler",
                title: currentSpoiler.title || "Spoiler",
                bodyMarkdown: currentSpoiler.body.join("\n"),
            });
            currentSpoiler = null;
            return;
        }

        if (currentSpoiler) {
            currentSpoiler.body.push(line);
            return;
        }

        markdownBuffer.push(line);
    });

    flushMarkdown();

    if (currentSpoiler) {
        blocks.push({
            type: "spoiler",
            title: currentSpoiler.title || "Spoiler",
            bodyMarkdown: currentSpoiler.body.join("\n"),
        });
    }

    if (mermaidBuffer !== null) {
        blocks.push({
            type: "mermaid",
            code: mermaidBuffer.join("\n"),
        });
    }

    return blocks;
}

export function collectReferencedArticleAssetIds(bodyMarkdown) {
    const assetIds = new Set();

    parseArticleMarkdown(bodyMarkdown).forEach((block) => {
        const assetId = block?.attrs?.["asset-id"];
        if (assetId) {
            assetIds.add(assetId);
        }
    });

    return assetIds;
}

export function parseDirectiveAttributes(rawAttrs) {
    const attrs = {};
    if (!rawAttrs) {
        return attrs;
    }

    for (const match of rawAttrs.matchAll(ATTRIBUTE_RE)) {
        attrs[match[1]] = match[2];
    }

    return attrs;
}

export function replaceSelection(textarea, replacement, fallbackSelection = "") {
    if (!textarea) {
        return { value: replacement, nextSelectionStart: replacement.length, nextSelectionEnd: replacement.length };
    }

    const start = textarea.selectionStart || 0;
    const end = textarea.selectionEnd || 0;
    const selectedText = textarea.value.slice(start, end) || fallbackSelection;
    const nextValue = textarea.value.slice(0, start) + replacement.replace("$SELECTION$", selectedText) + textarea.value.slice(end);
    const caretIndex = start + replacement.replace("$SELECTION$", selectedText).length;

    return {
        value: nextValue,
        nextSelectionStart: caretIndex,
        nextSelectionEnd: caretIndex,
    };
}

export function insertAtCursor(textarea, insertion) {
    return replaceSelection(textarea, insertion);
}

export function wrapSelection(textarea, before, after = "", fallbackSelection = "") {
    if (!textarea) {
        const value = `${before}${fallbackSelection}${after}`;
        return { value, nextSelectionStart: value.length, nextSelectionEnd: value.length };
    }

    const start = textarea.selectionStart || 0;
    const end = textarea.selectionEnd || 0;
    const selectedText = textarea.value.slice(start, end) || fallbackSelection;
    const insertedValue = `${before}${selectedText}${after}`;
    const nextValue = textarea.value.slice(0, start) + insertedValue + textarea.value.slice(end);
    const caretIndex = start + insertedValue.length;

    return {
        value: nextValue,
        nextSelectionStart: caretIndex,
        nextSelectionEnd: caretIndex,
    };
}

export function prefixSelectedLines(textarea, prefix, fallbackLine = "") {
    if (!textarea) {
        const value = `${prefix}${fallbackLine}`;
        return { value, nextSelectionStart: value.length, nextSelectionEnd: value.length };
    }

    const start = textarea.selectionStart || 0;
    const end = textarea.selectionEnd || 0;
    const lineStart = textarea.value.lastIndexOf("\n", Math.max(0, start - 1)) + 1;
    const lineEndIndex = textarea.value.indexOf("\n", end);
    const lineEnd = lineEndIndex === -1 ? textarea.value.length : lineEndIndex;
    const selectedBlock = textarea.value.slice(lineStart, lineEnd) || fallbackLine;
    const prefixedBlock = selectedBlock
        .split("\n")
        .map((line) => (line.trim() ? `${prefix}${line}` : prefix.trimEnd()))
        .join("\n");
    const nextValue = textarea.value.slice(0, lineStart) + prefixedBlock + textarea.value.slice(lineEnd);
    const caretIndex = lineStart + prefixedBlock.length;

    return {
        value: nextValue,
        nextSelectionStart: caretIndex,
        nextSelectionEnd: caretIndex,
    };
}

export function buildMermaidBlock(code) {
    return `\`\`\`mermaid\n${(code || "").trim()}\n\`\`\``;
}

export function buildMermaidPreviewUrl(code) {
    const normalizedCode = (code || "").trim();
    if (!normalizedCode) {
        return "";
    }

    const encoded = window.btoa(
        Array.from(new TextEncoder().encode(normalizedCode), (byte) => String.fromCharCode(byte)).join("")
    );
    return `https://mermaid.ink/svg/${encoded}`;
}

export function findMermaidBlockAtSelection(value, selectionStart = 0, selectionEnd = selectionStart) {
    let match;
    let index = 0;

    while ((match = MERMAID_BLOCK_RE.exec(value || "")) !== null) {
        const start = match.index;
        const end = start + match[0].length;
        if (
            (selectionStart >= start && selectionStart <= end)
            || (selectionEnd >= start && selectionEnd <= end)
            || (selectionStart <= start && selectionEnd >= end)
        ) {
            return {
                index,
                start,
                end,
                code: (match[1] || "").trim(),
            };
        }
        index += 1;
    }

    return null;
}

export function replaceMermaidBlockByIndex(value, targetIndex, nextCode) {
    let match;
    let index = 0;
    let nextValue = value || "";

    while ((match = MERMAID_BLOCK_RE.exec(value || "")) !== null) {
        if (index === targetIndex) {
            const start = match.index;
            const end = start + match[0].length;
            nextValue = (value || "").slice(0, start) + buildMermaidBlock(nextCode) + (value || "").slice(end);
            break;
        }
        index += 1;
    }

    return nextValue;
}

export function stripArticleFormatting(value) {
    return (value || "")
        .split("\n")
        .map((line) => line.trim())
        .filter(Boolean)
        .map((line) => (
            line
                .replace(LEADING_MARKDOWN_RE, "")
                .replace(IMAGE_LINK_RE, "$1")
                .replace(MARKDOWN_LINK_RE, "$1")
                .replace(INLINE_FORMATTING_RE, "")
                .replace(/\\/g, "")
                .trim()
        ))
        .filter(Boolean)
        .join(" ");
}
