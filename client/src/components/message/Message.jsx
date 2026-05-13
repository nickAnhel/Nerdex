import { useContext, useEffect, useState } from "react"
import { Link } from "react-router-dom";

import "./Message.css";

import { StoreContext } from "../..";
import DownloadIcon from "../icons/DownloadIcon";
import FileTypeIcon from "../icons/FileTypeIcon";
import { getAvatarUrl } from "../../utils/avatar";
import { formatAttachmentSize } from "../../utils/postAttachments";
import { getMessageReactionMeta } from "./messageReactions";


function Message({
    messageId,
    username,
    content,
    createdAt,
    avatarUrl = null,
    status = "sent",
    editedAt = null,
    deletedAt = null,
    replyPreview = null,
    attachments = [],
    sharedContent = null,
    reactions = [],
    isHighlighted = false,
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
    const visibleReactions = reactions.filter((reaction) => reaction.count > 0 || reaction.reactedByMe);

    return (
        <>
            <div
                id={messageId ? `message-${messageId}` : undefined}
                className={`${username === "You" ? "msg you" : "msg"} ${status !== "sent" ? `msg-${status}` : ""} ${isDeleted ? "msg-deleted" : ""} ${isHighlighted ? "msg-highlighted" : ""}`}
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
                    {visibleContent && <div className="msg-text">{visibleContent}</div>}
                    {!isDeleted && attachments.length > 0 && (
                        <MessageAttachments attachments={attachments} />
                    )}
                    {!isDeleted && sharedContent && (
                        <MessageSharedContentPreview content={sharedContent} />
                    )}
                    {visibleReactions.length > 0 && (
                        <MessageReactions reactions={visibleReactions} />
                    )}
                    {
                        status === "failed" && !isDeleted &&
                        <button className="msg-retry" type="button" onClick={onRetry}>Retry</button>
                    }
                </div>
            </div>
        </>
    )
}

function MessageReactions({ reactions = [] }) {
    return (
        <div className="msg-reactions" aria-label="Message reactions">
            {reactions.map((reaction) => {
                const meta = getMessageReactionMeta(reaction.reactionType);

                return (
                    <span
                        key={reaction.reactionType}
                        className={`msg-reaction-pill ${reaction.reactedByMe ? "msg-reaction-pill-active" : ""}`}
                        aria-label={`${meta.ariaLabel} ${reaction.count}`}
                    >
                        <span className="msg-reaction-pill-emoji" aria-hidden="true">
                            {meta.emoji}
                        </span>
                        <span className="msg-reaction-pill-count">{reaction.count}</span>
                    </span>
                );
            })}
        </div>
    );
}

function MessageSharedContentPreview({ content }) {
    const path = resolveContentPath(content);
    const imageUrl = resolveContentImage(content);
    const title = content.title || resolveContentTypeLabel(content.content_type);
    const body = content.excerpt || content.description || content.caption || content.post_content || "";

    return (
        <Link className="msg-shared-content" to={path}>
            {imageUrl && (
                <img
                    className="msg-shared-content-image"
                    src={imageUrl}
                    alt={title}
                />
            )}
            <span className="msg-shared-content-body">
                <span className="msg-shared-content-type">{resolveContentTypeLabel(content.content_type)}</span>
                <span className="msg-shared-content-title">{title}</span>
                {body && <span className="msg-shared-content-excerpt">{body}</span>}
                {content.user?.username && (
                    <span className="msg-shared-content-author">@{content.user.username}</span>
                )}
            </span>
        </Link>
    );
}

function resolveContentImage(content) {
    if (content.cover?.preview_url || content.cover?.poster_url || content.cover?.original_url) {
        return content.cover.preview_url || content.cover.poster_url || content.cover.original_url;
    }

    const firstMedia = content.media_attachments?.[0];
    return firstMedia?.preview_url || firstMedia?.original_url || null;
}

function resolveContentPath(content) {
    if (content.canonical_path) {
        return content.canonical_path;
    }
    if (content.content_type === "post") {
        return `/feed?p=${content.content_id}`;
    }
    if (content.content_type === "article") {
        return `/articles/${content.content_id}`;
    }
    if (content.content_type === "video") {
        return `/videos/${content.content_id}`;
    }
    if (content.content_type === "moment") {
        return `/moments?moment=${content.content_id}`;
    }
    return "/feed";
}

function resolveContentTypeLabel(contentType) {
    const labels = {
        post: "Post",
        article: "Article",
        video: "Video",
        moment: "Moment",
    };
    return labels[contentType] || "Content";
}

function MessageAttachments({ attachments = [] }) {
    return (
        <div className="msg-attachments">
            {attachments.map((attachment) => {
                const key = `${attachment.asset_id}-${attachment.position}`;
                const isImage = attachment.asset_type === "image" || attachment.file_kind === "image";
                const isVideo = attachment.asset_type === "video" || attachment.file_kind === "video";
                const mediaUrl = attachment.preview_url || attachment.original_url || attachment.stream_url;
                const metaParts = [
                    attachment.file_kind?.toUpperCase() || "FILE",
                    formatAttachmentSize(attachment.size_bytes),
                ].filter(Boolean);

                if (isImage && mediaUrl) {
                    return (
                        <a
                            key={key}
                            className="msg-attachment-media"
                            href={attachment.original_url || mediaUrl}
                            target="_blank"
                            rel="noreferrer"
                            onClick={(event) => event.stopPropagation()}
                        >
                            <img src={mediaUrl} alt={attachment.original_filename || "Image attachment"} />
                        </a>
                    );
                }

                if (isVideo && mediaUrl) {
                    return (
                        <video
                            key={key}
                            className="msg-attachment-video"
                            src={attachment.stream_url || attachment.original_url || mediaUrl}
                            poster={attachment.poster_url || undefined}
                            controls
                            preload="metadata"
                        />
                    );
                }

                return (
                    <div key={key} className="msg-attachment-file">
                        <span className="msg-attachment-file-icon" aria-hidden="true">
                            <FileTypeIcon kind={attachment.file_kind} />
                        </span>
                        <span className="msg-attachment-file-body">
                            <span className="msg-attachment-file-name">
                                {attachment.original_filename || "Untitled file"}
                            </span>
                            {metaParts.length > 0 && (
                                <span className="msg-attachment-file-meta">{metaParts.join(" . ")}</span>
                            )}
                        </span>
                        {attachment.download_url && (
                            <a
                                className="msg-attachment-download"
                                href={attachment.download_url}
                                target="_blank"
                                rel="noreferrer"
                                aria-label={`Download ${attachment.original_filename || "file"}`}
                                onClick={(event) => event.stopPropagation()}
                            >
                                <DownloadIcon />
                            </a>
                        )}
                    </div>
                );
        })}
    </div>
);
}

export default Message
