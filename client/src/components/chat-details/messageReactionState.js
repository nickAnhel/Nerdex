export function normalizeMessageReactions(reactions = []) {
    return reactions.map((reaction) => ({
        reactionType: reaction.reaction_type,
        count: reaction.count || 0,
        reactedByMe: Boolean(reaction.reacted_by_me),
    }));
}

export function applyReactionEventToMessage(messageItem, reactionEvent, currentUserId) {
    if (messageItem.type !== "message" || messageItem.messageId !== reactionEvent.message_id) {
        return messageItem;
    }

    return {
        ...messageItem,
        reactions: applyReactionEventToReactions(
            messageItem.reactions || [],
            reactionEvent,
            currentUserId,
        ),
    };
}

export function applyReactionEventToReactions(reactions, reactionEvent, currentUserId) {
    const nextReactions = reactions.map((reaction) => ({ ...reaction }));
    const byType = new Map(nextReactions.map((reaction) => [reaction.reactionType, reaction]));
    const actorIsMe = reactionEvent.user_id === currentUserId;
    const countDelta = reactionEvent.action === "added" ? 1 : -1;

    const updateReaction = (reactionType, delta, setReactedByMe) => {
        if (!reactionType) {
            return;
        }

        const reaction = byType.get(reactionType);
        if (!reaction) {
            return;
        }

        reaction.count = Math.max(0, (reaction.count || 0) + delta);
        if (setReactedByMe !== undefined) {
            reaction.reactedByMe = setReactedByMe;
        }
    };

    if (reactionEvent.action === "added") {
        updateReaction(reactionEvent.previous_reaction_type, -1, actorIsMe ? false : undefined);
        updateReaction(reactionEvent.reaction_type, countDelta, actorIsMe ? true : undefined);
    } else if (reactionEvent.action === "removed") {
        updateReaction(reactionEvent.reaction_type, countDelta, actorIsMe ? false : undefined);
    }

    return nextReactions;
}
