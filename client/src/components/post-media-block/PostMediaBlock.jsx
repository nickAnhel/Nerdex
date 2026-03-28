import "./PostMediaBlock.css";


const FEED_MEDIA_LIMIT = 4;


function PostMediaBlock({ attachments = [], variant = "feed", onMediaClick }) {
    if (!attachments.length) {
        return null;
    }

    const isFeed = variant === "feed";
    const visibleAttachments = isFeed ? attachments.slice(0, FEED_MEDIA_LIMIT) : attachments;
    const hiddenCount = Math.max(attachments.length - visibleAttachments.length, 0);

    return (
        <div className={`post-media-block ${variant}`}>
            {visibleAttachments.map((attachment, index) => {
                const actualIndex = attachments.findIndex((item) => item.asset_id === attachment.asset_id);
                const isLastVisible = index === visibleAttachments.length - 1;

                return (
                    <button
                        key={`${attachment.asset_id}-${attachment.position}`}
                        type="button"
                        className="post-media-tile"
                        onClick={() => onMediaClick?.(actualIndex)}
                    >
                        {attachment.asset_type === "video" ? (
                            <video
                                src={attachment.preview_url || attachment.original_url}
                                poster={attachment.poster_url || undefined}
                                muted
                                playsInline
                                preload="metadata"
                            />
                        ) : (
                            <img
                                src={attachment.preview_url || attachment.original_url}
                                alt={attachment.original_filename || "Post media"}
                            />
                        )}
                        {attachment.asset_type === "video" && (
                            <span className="post-media-video-badge">
                                <span className="post-media-play-indicator" />
                                <span>Video</span>
                            </span>
                        )}
                        {hiddenCount > 0 && isLastVisible && (
                            <span className="post-media-more-indicator">+{hiddenCount}</span>
                        )}
                    </button>
                );
            })}
        </div>
    );
}

export default PostMediaBlock;
