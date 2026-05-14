import "./PostGalleryViewer.css";

import ChevronIcon from "../icons/ChevronIcon";
import CloseIcon from "../icons/CloseIcon";
import Modal from "../modal/Modal";
import VideoPlayer from "../video-player";


function buildVideoSources(attachment) {
    const sourceUrl = attachment?.stream_url || attachment?.original_url || attachment?.preview_url;
    if (!sourceUrl) {
        return [];
    }

    return [{
        id: "original",
        label: "Original",
        src: sourceUrl,
        mimeType: attachment.mime_type || attachment.declared_mime_type || "",
        isOriginal: true,
    }];
}


function PostGalleryViewer({ attachments = [], activeIndex, onClose, onChange }) {
    const isActive = activeIndex !== null && activeIndex >= 0 && activeIndex < attachments.length;
    const attachment = isActive ? attachments[activeIndex] : null;

    if (!isActive || !attachment) {
        return null;
    }

    const hasMultipleItems = attachments.length > 1;
    const handlePrevious = () => {
        if (!hasMultipleItems) {
            return;
        }
        onChange((activeIndex - 1 + attachments.length) % attachments.length);
    };
    const handleNext = () => {
        if (!hasMultipleItems) {
            return;
        }
        onChange((activeIndex + 1) % attachments.length);
    };

    return (
        <Modal active={isActive} setActive={() => onClose()}>
            <div className="post-gallery-viewer">
                <div className="post-gallery-toolbar">
                    <span>{activeIndex + 1} / {attachments.length}</span>
                    <button type="button" className="post-gallery-close" onClick={() => onClose()} aria-label="Close gallery">
                        <CloseIcon />
                    </button>
                </div>

                <div className="post-gallery-frame">
                    <button
                        type="button"
                        className="post-gallery-nav"
                        onClick={handlePrevious}
                        disabled={!hasMultipleItems}
                        aria-label="Previous media"
                    >
                        <ChevronIcon direction="left" />
                    </button>

                    <div className="post-gallery-media">
                        {attachment.asset_type === "video" ? (
                            <VideoPlayer
                                skin="post"
                                sources={buildVideoSources(attachment)}
                                posterUrl={attachment.poster_url || undefined}
                                title={attachment.original_filename || "Post video"}
                                preload="metadata"
                            />
                        ) : (
                            <img
                                src={attachment.original_url || attachment.preview_url}
                                alt={attachment.original_filename || "Post media"}
                            />
                        )}
                    </div>

                    <button
                        type="button"
                        className="post-gallery-nav"
                        onClick={handleNext}
                        disabled={!hasMultipleItems}
                        aria-label="Next media"
                    >
                        <ChevronIcon direction="right" />
                    </button>
                </div>
            </div>
        </Modal>
    );
}

export default PostGalleryViewer;
