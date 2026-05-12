import { useContext, useEffect, useState } from "react"
import { Link } from "react-router-dom";

import "./Message.css";

import { StoreContext } from "../..";
import DownloadIcon from "../icons/DownloadIcon";
import FileTypeIcon from "../icons/FileTypeIcon";
import { getAvatarUrl } from "../../utils/avatar";
import { formatAttachmentSize } from "../../utils/postAttachments";


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
    attachments = [],
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
                    {visibleContent && <div className="msg-text">{visibleContent}</div>}
                    {!isDeleted && attachments.length > 0 && (
                        <MessageAttachments attachments={attachments} />
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
