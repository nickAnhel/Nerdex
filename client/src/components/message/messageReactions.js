export const MESSAGE_REACTIONS = [
    {
        reactionType: "like",
        emoji: "👍",
        ariaLabel: "Like",
    },
    {
        reactionType: "dislike",
        emoji: "👎",
        ariaLabel: "Dislike",
    },
    {
        reactionType: "heart",
        emoji: "❤️",
        ariaLabel: "Heart",
    },
    {
        reactionType: "fire",
        emoji: "🔥",
        ariaLabel: "Fire",
    },
    {
        reactionType: "joy",
        emoji: "😂",
        ariaLabel: "Laugh",
    },
    {
        reactionType: "cry",
        emoji: "😢",
        ariaLabel: "Cry",
    },
    {
        reactionType: "thinking",
        emoji: "🤔",
        ariaLabel: "Thinking",
    },
    {
        reactionType: "exploding_head",
        emoji: "🤯",
        ariaLabel: "Mind blown",
    },
    {
        reactionType: "clap",
        emoji: "👏",
        ariaLabel: "Clap",
    },
    {
        reactionType: "pray",
        emoji: "🙏",
        ariaLabel: "Pray",
    },
];

export function getMessageReactionMeta(reactionType) {
    return MESSAGE_REACTIONS.find((reaction) => reaction.reactionType === reactionType) || {
        reactionType,
        emoji: "❓",
        ariaLabel: reactionType,
    };
}
