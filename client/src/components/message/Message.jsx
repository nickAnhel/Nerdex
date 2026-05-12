import { useContext, useEffect, useState } from "react"
import { Link } from "react-router-dom";

import "./Message.css";

import { StoreContext } from "../..";
import { getAvatarUrl } from "../../utils/avatar";


function Message({
    messageId,
    userId,
    username,
    content,
    createdAt,
    avatarUrl = null,
    status = "sent",
    editedAt = null,
    deletedAt = null,
    replyPreview = null,
    onContextMenu,
    onReplyPreviewClick,
    onRetry,
}) {
    const { store } = useContext(StoreContext);

    const createdAtTimeLocal = createdAt
        ? new Date(createdAt).toLocaleTimeString().split(":").slice(0, 2).join(":")
        : "";
    const [userProfilePhotoSrc, setUserProfilePhotoSrc] = useState(
        avatarUrl || (username === "You" ? getAvatarUrl(store.user, "small") : "/assets/profile.svg")
    );

    useEffect(() => {
        setUserProfilePhotoSrc(
            avatarUrl || (username === "You" ? getAvatarUrl(store.user, "small") : "/assets/profile.svg")
        );
    }, [avatarUrl, store.user, username]);

    const isDeleted = Boolean(deletedAt);
    const visibleContent = isDeleted ? "Message deleted" : content;

    return (
        <>
            <div
                id={messageId ? `message-${messageId}` : undefined}
                className={`${username === "You" ? "msg you" : "msg"} ${status !== "sent" ? `msg-${status}` : ""} ${isDeleted ? "msg-deleted" : ""}`}
                onContextMenu={onContextMenu}
            >
                <Link to={`/people/@${username === "You" ? store.user.username : username}`}>
                    <img
                        src={userProfilePhotoSrc}
                        onError={() => { setUserProfilePhotoSrc("/assets/profile.svg") }}
                        alt={username}
                    />
                </Link>
                <div className="msg-info">
                    <div className="msg-label">
                        <div className="username">{username}</div>
                        <div>
                            {status === "pending" ? "Sending" : createdAtTimeLocal}
                            {!isDeleted && editedAt && " edited"}
                        </div>
                    </div>
                    {
                        replyPreview &&
                        <button
                            className={`msg-reply-preview ${replyPreview.deleted ? "msg-reply-preview-deleted" : ""}`}
                            type="button"
                            onClick={() => onReplyPreviewClick?.(replyPreview.messageId)}
                        >
                            <span>{replyPreview.senderDisplayName}</span>
                            <p>{replyPreview.contentPreview}</p>
                        </button>
                    }
                    <div className="msg-text">{visibleContent}</div>
                    {
                        status === "failed" && !isDeleted &&
                        <button className="msg-retry" type="button" onClick={onRetry}>Retry</button>
                    }
                </div>
            </div>
        </>
    )
}

export default Message
