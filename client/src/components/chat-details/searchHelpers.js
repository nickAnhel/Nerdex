const DEFAULT_SNIPPET_LENGTH = 160;

function escapeRegExp(value) {
    return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

export function normalizeSearchText(text) {
    return (text || "").replace(/\s+/g, " ").trim();
}

export function buildSearchSnippet(text, query, maxLength = DEFAULT_SNIPPET_LENGTH) {
    const normalizedText = normalizeSearchText(text);
    if (!normalizedText) {
        return "";
    }

    const normalizedQuery = normalizeSearchText(query);
    if (!normalizedQuery || normalizedText.length <= maxLength) {
        return normalizedText;
    }

    const lowerText = normalizedText.toLowerCase();
    const lowerQuery = normalizedQuery.toLowerCase();
    const matchIndex = lowerText.indexOf(lowerQuery);

    if (matchIndex === -1) {
        const cutText = normalizedText.slice(0, maxLength);
        return `${cutText}${normalizedText.length > maxLength ? "..." : ""}`;
    }

    const windowSize = Math.max(maxLength - normalizedQuery.length, 0);
    const leftPadding = Math.floor(windowSize / 2);
    const start = Math.max(matchIndex - leftPadding, 0);
    const end = Math.min(start + maxLength, normalizedText.length);

    return `${start > 0 ? "..." : ""}${normalizedText.slice(start, end).trim()}${end < normalizedText.length ? "..." : ""}`;
}

export function splitHighlightedText(text, query) {
    const normalizedText = text || "";
    const normalizedQuery = normalizeSearchText(query);

    if (!normalizedQuery) {
        return [{ text: normalizedText, highlighted: false }];
    }

    const regex = new RegExp(`(${escapeRegExp(normalizedQuery)})`, "ig");
    const parts = normalizedText.split(regex).filter(Boolean);

    return parts.map((part) => ({
        text: part,
        highlighted: part.toLowerCase() === normalizedQuery.toLowerCase(),
    }));
}
