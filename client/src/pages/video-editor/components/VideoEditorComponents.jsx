import TagInput from "../../../components/tag-input/TagInput";
import { formatDuration } from "../../../components/video-card/VideoCard";


const ASSET_STATUS_LABELS = {
    empty: "No file selected",
    pending_upload: "Waiting for upload",
    selected: "Selected",
    uploaded: "Uploaded",
    uploading: "Uploading",
    processing: "Processing",
    ready: "Ready",
    failed: "Failed",
    error: "Failed",
    deleted: "Deleted",
};

function formatBytes(bytes) {
    if (!Number.isFinite(Number(bytes))) {
        return "";
    }
    const value = Number(bytes);
    if (value >= 1024 * 1024) {
        return `${(value / 1024 / 1024).toFixed(1)} MB`;
    }
    if (value >= 1024) {
        return `${(value / 1024).toFixed(1)} KB`;
    }
    return `${value} B`;
}

function statusLabel(status) {
    return ASSET_STATUS_LABELS[status] || status || "No file selected";
}

export function VideoProcessingStatusPanel({ sourceAsset, coverAsset, assetUploadStates }) {
    return (
        <section className="video-asset-status-panel" aria-label="Video asset upload statuses">
            <AssetStatusItem label="Video file" asset={sourceAsset} uploadState={assetUploadStates.source} />
            <AssetStatusItem label="Cover image" asset={coverAsset} uploadState={assetUploadStates.cover} />
        </section>
    );
}

function AssetStatusItem({ label, asset, uploadState }) {
    const effectiveStatus = uploadState || asset?.status || "empty";
    const readyVariantCount = asset?.variants?.filter((variant) => variant.status === "ready").length || 0;

    return (
        <div className="video-asset-status-item">
            <div>
                <strong>{label}</strong>
                <span>{asset?.original_filename || "No file selected"}</span>
            </div>
            <div className="video-asset-status-meta">
                <span className={`video-asset-status-value ${effectiveStatus}`}>
                    {statusLabel(effectiveStatus)}
                </span>
                {
                    asset &&
                    <span>{readyVariantCount}/{asset.variants?.length || 0} variants ready</span>
                }
            </div>
        </div>
    );
}

export function VideoSourcePicker({
    sourceAsset,
    selectedSourceFile,
    metadata,
    localVideoUrl,
    isUploading,
    onVideoFile,
    children,
}) {
    const fileName = selectedSourceFile?.name || sourceAsset?.original_filename;
    const size = selectedSourceFile?.size || sourceAsset?.size_bytes;
    const duration = metadata?.duration || sourceAsset?.duration_ms / 1000;
    const width = metadata?.width || sourceAsset?.width;
    const height = metadata?.height || sourceAsset?.height;
    const orientation = metadata?.orientation || (width && height ? (width === height ? "square" : width > height ? "landscape" : "portrait") : "");

    return (
        <section className="video-editor-panel">
            <label className="video-file-drop">
                <span>Video source</span>
                <input
                    type="file"
                    accept="video/mp4,video/webm,video/quicktime,.mp4,.webm,.mov"
                    onChange={(event) => onVideoFile(event.target.files?.[0])}
                    disabled={isUploading}
                />
            </label>
            <div className="video-editor-metadata">
                <span>{fileName || "No video selected"}</span>
                {size ? <span>{formatBytes(size)}</span> : null}
                {duration ? <span>{formatDuration(duration)}</span> : null}
                {width && height ? <span>{Math.round(width)}x{Math.round(height)}</span> : null}
                {orientation ? <span>{orientation}</span> : null}
            </div>
            {localVideoUrl ? children : null}
        </section>
    );
}

export function VideoFramePicker({
    localVideoUrl,
    videoRef,
    canvasRef,
    metadata,
    frameSecond,
    isUploading,
    onLoadedMetadata,
    onFrameChange,
    onUseSelectedFrame,
}) {
    if (!localVideoUrl) {
        return null;
    }

    return (
        <div className="video-frame-picker">
            <video
                ref={videoRef}
                src={localVideoUrl}
                preload="metadata"
                controls
                onLoadedMetadata={onLoadedMetadata}
            />
            {
                metadata?.duration > 0 &&
                <>
                    <label>
                        Selected frame {formatDuration(frameSecond)}
                        <input
                            type="range"
                            min="0"
                            max={metadata.duration}
                            step="0.1"
                            value={frameSecond}
                            onChange={(event) => onFrameChange(event.target.value)}
                        />
                    </label>
                    <button type="button" onClick={onUseSelectedFrame} disabled={isUploading}>
                        Use selected frame
                    </button>
                </>
            }
            <canvas ref={canvasRef} hidden />
        </div>
    );
}

export function VideoCoverPicker({ coverAsset, localCoverUrl, isUploading, onCoverFile }) {
    return (
        <section className="video-editor-panel">
            <label>
                Cover image
                <input
                    type="file"
                    accept="image/jpeg,image/png,image/webp,image/gif,.jpg,.jpeg,.png,.webp,.gif"
                    onChange={(event) => onCoverFile(event.target.files?.[0])}
                    disabled={isUploading}
                />
            </label>
            <div className="video-editor-metadata">
                <span>{coverAsset?.original_filename || "Cover is required"}</span>
                {coverAsset?.size_bytes ? <span>{formatBytes(coverAsset.size_bytes)}</span> : null}
            </div>
            {
                localCoverUrl &&
                <div className="video-cover-preview">
                    <img src={localCoverUrl} alt="Selected video cover" />
                </div>
            }
        </section>
    );
}

export function VideoPublishSettings({ form, updateField, tagInputState, setTagInputState }) {
    return (
        <section className="video-editor-panel">
            <label>
                Title
                <input
                    type="text"
                    value={form.title}
                    maxLength={300}
                    onChange={(event) => updateField("title", event.target.value)}
                    placeholder="Video title"
                />
            </label>
            <label>
                Description
                <textarea
                    value={form.description}
                    maxLength={4000}
                    onChange={(event) => updateField("description", event.target.value)}
                    placeholder="Describe the video"
                />
            </label>
            <label>
                Visibility
                <select
                    value={form.visibility}
                    onChange={(event) => updateField("visibility", event.target.value)}
                >
                    <option value="private">Private</option>
                    <option value="public">Public</option>
                </select>
            </label>
            <TagInput
                tags={form.tags}
                onChange={(tags) => updateField("tags", tags)}
                onInputStateChange={setTagInputState}
            />
            {tagInputState.error ? <p className="video-editor-error inline">{tagInputState.error}</p> : null}
        </section>
    );
}

export function VideoChaptersEditor({
    chapters,
    frameSecond,
    durationSeconds,
    validationErrors,
    onAddAtCurrentTime,
    onUpdateChapter,
    onUpdateChapterTime,
    onRemoveChapter,
}) {
    return (
        <section className="video-editor-panel video-chapters">
            <div className="video-chapters-header">
                <h2>Chapters</h2>
                <button type="button" onClick={() => onAddAtCurrentTime(frameSecond || 0)}>
                    Add chapter at current time
                </button>
            </div>
            {
                chapters.map((chapter, index) => (
                    <div className="video-chapter-row" key={`${index}-${chapter.startsAtSeconds}`}>
                        <input
                            type="text"
                            value={chapter.title}
                            maxLength={120}
                            onChange={(event) => onUpdateChapter(index, { title: event.target.value })}
                            placeholder="Chapter title"
                        />
                        <input
                            type="text"
                            inputMode="numeric"
                            value={chapter.timeInput ?? formatDuration(chapter.startsAtSeconds)}
                            onChange={(event) => onUpdateChapterTime(index, event.target.value)}
                            placeholder={durationSeconds >= 3600 ? "0:00:00" : "0:00"}
                            aria-label="Chapter start time"
                        />
                        <span>{formatDuration(chapter.startsAtSeconds)}</span>
                        <button type="button" onClick={() => onRemoveChapter(index)}>Remove</button>
                    </div>
                ))
            }
            {validationErrors.map((error) => <p className="video-editor-error inline" key={error}>{error}</p>)}
        </section>
    );
}
