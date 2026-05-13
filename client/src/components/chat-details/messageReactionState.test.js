import { applyReactionEventToReactions } from "./messageReactionState";


test("reaction updates preserve other users' reactedByMe state", () => {
    const reactions = [
        { reactionType: "like", count: 2, reactedByMe: true },
        { reactionType: "heart", count: 0, reactedByMe: false },
    ];

    const next = applyReactionEventToReactions(
        reactions,
        {
            message_id: "message-1",
            user_id: "another-user",
            reaction_type: "heart",
            previous_reaction_type: null,
            action: "added",
        },
        "current-user",
    );

    expect(next[0].count).toBe(2);
    expect(next[0].reactedByMe).toBe(true);
    expect(next[1].count).toBe(1);
    expect(next[1].reactedByMe).toBe(false);
});

test("reaction updates mark current user's reaction on broadcast events", () => {
    const reactions = [
        { reactionType: "like", count: 1, reactedByMe: false },
        { reactionType: "heart", count: 0, reactedByMe: false },
    ];

    const next = applyReactionEventToReactions(
        reactions,
        {
            message_id: "message-1",
            user_id: "current-user",
            reaction_type: "heart",
            previous_reaction_type: "like",
            action: "added",
        },
        "current-user",
    );

    expect(next[0].count).toBe(0);
    expect(next[0].reactedByMe).toBe(false);
    expect(next[1].count).toBe(1);
    expect(next[1].reactedByMe).toBe(true);
});
