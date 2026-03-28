import "./PostFileBlock.css";

import DownloadIcon from "../icons/DownloadIcon";
import FileTypeIcon from "../icons/FileTypeIcon";
import PostAudioPlayer from "../post-audio-player/PostAudioPlayer";
import { formatAttachmentSize } from "../../utils/postAttachments";


const FEED_FILE_LIMIT = 3;


function PostFileBlock({ attachments = [], variant = "feed" }) {
    if (!attachments.length) {
        return null;
    }

    const isFeed = variant === "feed";
    const visibleAttachments = isFeed ? attachments.slice(0, FEED_FILE_LIMIT) : attachments;
    const hiddenCount = Math.max(attachments.length - visibleAttachments.length, 0);

    return (
        <div className={`post-file-block ${variant}`}>
            {visibleAttachments.map((attachment) => {
                const metaParts = [
                    attachment.file_kind?.toUpperCase() || "FILE",
                    formatAttachmentSize(attachment.size_bytes),
                ].filter(Boolean);

                const cardBody = (
                    <div className="post-file-card">
                        <span className="post-file-icon" aria-hidden="true">
                            <FileTypeIcon kind={attachment.file_kind} />
                        </span>
                        <span className="post-file-body">
                            <span className="post-file-name">{attachment.original_filename || "Untitled file"}</span>
                            {metaParts.length > 0 && (
                                <span className="post-file-meta">{metaParts.join(" . ")}</span>
                            )}
                        </span>
                            {attachment.is_audio && attachment.stream_url && (
                                <PostAudioPlayer
                                    src={attachment.stream_url}
                                    durationMs={attachment.duration_ms}
                                />
                            )}
                        {attachment.download_url && (
                            <a
                                className="post-file-download-button"
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

                return (
                    <div key={`${attachment.asset_id}-${attachment.position}`} className="post-file-item">
                        {cardBody}
                    </div>
                );
            })}

            {hiddenCount > 0 && (
                <div className="post-file-more-card">+{hiddenCount} more files</div>
            )}
        </div>
    );
}

export default PostFileBlock;
