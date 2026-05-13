import {
    getTypingIndicatorText,
    removeTypingUser,
    upsertTypingUser,
} from "./typingState";


test("typing indicator uses direct chat phrasing for a single user", () => {
    expect(getTypingIndicatorText([
        { userId: "user-1", username: "Alice" },
    ], "direct")).toBe("Alice typing...");
});


test("typing indicator uses group chat phrasing for one user", () => {
    expect(getTypingIndicatorText([
        { userId: "user-1", username: "Alice" },
    ], "group")).toBe("Alice typing...");
});


test("typing indicator uses group plural phrasing for multiple users", () => {
    expect(getTypingIndicatorText([
        { userId: "user-1", username: "Alice" },
        { userId: "user-2", username: "Bob" },
        { userId: "user-3", username: "Cara" },
    ], "group")).toBe("Alice and 2 others typing...");
});


test("upsertTypingUser keeps the latest user last and removes duplicates", () => {
    const result = upsertTypingUser([
        { userId: "user-1", username: "Alice" },
        { userId: "user-2", username: "Bob" },
    ], { userId: "user-1", username: "Alice" });

    expect(result).toEqual([
        { userId: "user-2", username: "Bob" },
        { userId: "user-1", username: "Alice" },
    ]);
});


test("removeTypingUser removes the matching user only", () => {
    expect(removeTypingUser([
        { userId: "user-1", username: "Alice" },
        { userId: "user-2", username: "Bob" },
    ], "user-1")).toEqual([
        { userId: "user-2", username: "Bob" },
    ]);
});
