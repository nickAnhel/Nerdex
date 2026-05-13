import { buildSearchSnippet, splitHighlightedText } from "./searchHelpers";


describe("searchHelpers", () => {
    it("builds a short snippet around the match", () => {
        const snippet = buildSearchSnippet(
            "The quick brown fox jumps over the lazy dog",
            "brown",
            18,
        );

        expect(snippet).toContain("brown");
        expect(snippet.startsWith("...")).toBe(true);
    });

    it("splits highlighted text case-insensitively", () => {
        const parts = splitHighlightedText("Hello hello world", "hello");

        expect(parts).toEqual([
            { text: "Hello", highlighted: true },
            { text: " ", highlighted: false },
            { text: "hello", highlighted: true },
            { text: " world", highlighted: false },
        ]);
    });
});
