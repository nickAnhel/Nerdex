export const TYPING_STATUS_TIMEOUT_MS = 6000;
export const TYPING_START_THROTTLE_MS = 2000;

export function upsertTypingUser(typingUsers = [], nextUser) {
    const remainingUsers = typingUsers.filter((typingUser) => typingUser.userId !== nextUser.userId);
    return [...remainingUsers, nextUser];
}

export function removeTypingUser(typingUsers = [], userId) {
    return typingUsers.filter((typingUser) => typingUser.userId !== userId);
}

export function getTypingIndicatorText(typingUsers = [], chatType) {
    if (typingUsers.length === 0) {
        return "";
    }

    const [firstUser, ...otherUsers] = typingUsers;
    const otherCount = otherUsers.length;

    if (chatType !== "group" || otherCount === 0) {
        return `${firstUser.username} typing...`;
    }

    return `${firstUser.username} and ${otherCount} other${otherCount === 1 ? "" : "s"} typing...`;
}
