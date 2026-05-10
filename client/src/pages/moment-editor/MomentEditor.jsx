import { useContext, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import "./MomentEditor.css";

import { StoreContext } from "../..";
import Loader from "../../components/loader/Loader";
import TagInput from "../../components/tag-input/TagInput";
import Unauthorized from "../../components/unauthorized/Unauthorized";
import { formatDuration } from "../../components/video-card/VideoCard";
import MomentService from "../../service/MomentService";
import {
    VideoCoverPicker,
    VideoFramePicker,
    VideoProcessingStatusPanel,
    VideoSourcePicker,
} from "../video-editor/components/VideoEditorComponents";
import useVideoFramePicker from "../video-editor/hooks/useVideoFramePicker";
import useVideoUploadFlow from "../video-editor/hooks/useVideoUploadFlow";


function tagsToSlugs(tags = []) {
    return tags.map((tag) => tag.slug || tag.name || tag).filter(Boolean);
}

function deriveOrientation(width, height) {
    if (!width || !height) {
        return "";
    }
    if (width === height) {
        return "square";
    }
    return width > height ? "landscape" : "portrait";
}

function momentMetadata(moment, sourceAsset) {
    const width = moment?.width || sourceAsset?.width || 0;
    const height = moment?.height || sourceAsset?.height || 0;
    return {
        duration: moment?.duration_seconds || (sourceAsset?.duration_ms ? sourceAsset.duration_ms / 1000 : 0),
        width,
        height,
        orientation: moment?.orientation || deriveOrientation(width, height),
    };
}

function validationErrorForMoment({ metadata, sourceAsset, moment }) {
    const effectiveMetadata = metadata || momentMetadata(moment, sourceAsset);
    const duration = effectiveMetadata.duration || 0;
    const orientation = effectiveMetadata.orientation || deriveOrientation(effectiveMetadata.width, effectiveMetadata.height);

    if (orientation && orientation !== "portrait") {
        return "Moments require portrait video.";
    }
    if (duration > 90) {
        return "Moments can be at most 90 seconds.";
    }
    if ((sourceAsset?.status === "ready" || moment?.processing_status === "ready") && !duration) {
        return "Video duration metadata is not available yet.";
    }
    return "";
}

function MomentEditor() {
    const { store } = useContext(StoreContext);
    const { momentId } = useParams();
    const navigate = useNavigate();
    const isEditing = Boolean(momentId);

    const [caption, setCaption] = useState("");
    const [tags, setTags] = useState([]);
    const [tagInputState, setTagInputState] = useState({ value: "", normalizedValue: "", error: "" });
    const [visibility, setVisibility] = useState("private");
    const [isLoading, setIsLoading] = useState(isEditing);
    const [isSaving, setIsSaving] = useState(false);
    const [publishAttempted, setPublishAttempted] = useState(false);
    const [publishNotice, setPublishNotice] = useState("");
    const [momentState, setMomentState] = useState(null);
    const [error, setError] = useState("");

    const uploadFlow = useVideoUploadFlow({
        onSourceReplaced: () => {
            setPublishNotice("Video source changed. Choose a new cover before saving.");
        },
    });
    const framePicker = useVideoFramePicker({
        onCoverCaptured: uploadFlow.handleCoverFile,
    });

    useEffect(() => {
        if (!isEditing) {
            return;
        }

        const loadMoment = async () => {
            setIsLoading(true);
            setError("");
            try {
                const res = await MomentService.getMomentEditor(momentId);
                const moment = res.data;
                setCaption(moment.caption || "");
                setTags(tagsToSlugs(moment.tags || []));
                setVisibility(moment.visibility || "private");
                setMomentState(moment);
                uploadFlow.loadAssets({
                    source: moment.source_asset,
                    cover: moment.cover,
                });
                framePicker.setMetadata(momentMetadata(moment, moment.source_asset));
            } catch (loadError) {
                setError(loadError?.response?.data?.detail || "Failed to load Moment.");
            } finally {
                setIsLoading(false);
            }
        };

        void loadMoment();
    }, [isEditing, momentId]); // eslint-disable-line react-hooks/exhaustive-deps

    useEffect(() => {
        if (
            !momentId
            || !momentState?.publish_requested_at
            || momentState.status === "published"
            || momentState.processing_error
            || momentState.processing_status === "failed"
        ) {
            return undefined;
        }

        const intervalId = window.setInterval(async () => {
            try {
                const res = await MomentService.getMomentEditor(momentId);
                const nextMoment = res.data;
                setMomentState(nextMoment);
                setCaption(nextMoment.caption || "");
                setTags(tagsToSlugs(nextMoment.tags || []));
                setVisibility(nextMoment.visibility || "private");
                uploadFlow.loadAssets({
                    source: nextMoment.source_asset || null,
                    cover: nextMoment.cover || null,
                });
                framePicker.setMetadata(momentMetadata(nextMoment, nextMoment.source_asset));

                if (nextMoment.status === "published") {
                    navigate(`/moments?moment=${nextMoment.moment_id || nextMoment.content_id}`);
                }
            } catch (pollError) {
                setError(pollError?.response?.data?.detail || "Failed to refresh Moment processing status.");
            }
        }, 5000);

        return () => window.clearInterval(intervalId);
    // Polling is tied to the current persisted Moment, while upload/frame hook objects
    // intentionally keep mutable editor state outside this dependency list.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [
        momentId,
        momentState?.publish_requested_at,
        momentState?.status,
        momentState?.processing_error,
        momentState?.processing_status,
        navigate,
    ]);

    const sourcePreviewUrl = uploadFlow.localVideoUrl
        || uploadFlow.sourceAsset?.original_url
        || uploadFlow.sourceAsset?.preview_url
        || "";

    const localValidationError = useMemo(() => validationErrorForMoment({
        metadata: framePicker.metadata,
        sourceAsset: uploadFlow.sourceAsset,
        moment: momentState,
    }), [framePicker.metadata, momentState, uploadFlow.sourceAsset]);

    const canSave = useMemo(() => (
        uploadFlow.canUseAssets
        && !isSaving
        && caption.length <= 2200
        && !tagInputState.error
        && !localValidationError
    ), [caption.length, isSaving, localValidationError, tagInputState.error, uploadFlow.canUseAssets]);

    const showStatusPanel = publishAttempted
        || Boolean(momentState?.publish_requested_at)
        || Boolean(uploadFlow.sourceAsset)
        || Boolean(uploadFlow.coverAsset);

    const saveMoment = async (status) => {
        if (!canSave) {
            setError(
                localValidationError
                || tagInputState.error
                || "Choose a video source and required cover before saving."
            );
            return;
        }
        if (status === "published") {
            setPublishAttempted(true);
        }
        setIsSaving(true);
        setError("");
        setPublishNotice("");
        const payload = {
            source_asset_id: uploadFlow.sourceAsset.asset_id,
            cover_asset_id: uploadFlow.coverAsset.asset_id,
            caption,
            tags,
            visibility,
            status,
        };
        try {
            const res = isEditing
                ? await MomentService.updateMoment(momentId, payload)
                : await MomentService.createMoment(payload);
            const saved = res.data;
            const savedMomentId = saved.moment_id || saved.content_id;
            setMomentState(saved);
            uploadFlow.loadAssets({
                source: saved.source_asset || uploadFlow.sourceAsset,
                cover: saved.cover || uploadFlow.coverAsset,
            });

            if (status === "published" && saved.status === "published") {
                navigate(`/moments?moment=${savedMomentId}`);
            } else if (status === "published") {
                setPublishNotice("Publishing requested. The Moment will publish after processing finishes.");
                if (!isEditing) {
                    navigate(`/moments/${savedMomentId}/edit`, { replace: true });
                }
            } else if (!isEditing) {
                setPublishNotice("Draft saved.");
                navigate(`/moments/${savedMomentId}/edit`, { replace: true });
            } else {
                setPublishNotice("Draft saved.");
            }
        } catch (saveError) {
            setError(saveError?.response?.data?.detail || "Failed to save Moment.");
        } finally {
            setIsSaving(false);
        }
    };

    const captureCover = async () => {
        try {
            await framePicker.captureCover();
        } catch (captureError) {
            setError(captureError.message || "Failed to capture cover frame.");
        }
    };

    if (!store.isAuthenticated) {
        return <Unauthorized />;
    }

    if (isLoading) {
        return (
            <main className="moment-editor-page">
                <Loader />
            </main>
        );
    }

    return (
        <main className="moment-editor-page">
            <header className="moment-editor-header">
                <div>
                    <h1>{isEditing ? "Edit Moment" : "New Moment"}</h1>
                    <p>Short portrait video, cover, caption, tags, and publish state.</p>
                </div>
                <Link to="/moments">Back to Moments</Link>
            </header>

            {(error || uploadFlow.uploadError || localValidationError || momentState?.processing_error) && (
                <p className="moment-editor-error">
                    {error || uploadFlow.uploadError || localValidationError || momentState?.processing_error}
                </p>
            )}
            {(publishNotice || uploadFlow.notice) && (
                <p className="moment-editor-notice">{publishNotice || uploadFlow.notice}</p>
            )}

            {showStatusPanel && (
                <>
                    <VideoProcessingStatusPanel
                        sourceAsset={uploadFlow.sourceAsset}
                        coverAsset={uploadFlow.coverAsset}
                        assetUploadStates={uploadFlow.assetUploadStates}
                    />
                    <MomentProcessingSummary moment={momentState} metadata={framePicker.metadata} />
                </>
            )}

            <section className="moment-editor-layout">
                <VideoSourcePicker
                    sourceAsset={uploadFlow.sourceAsset}
                    selectedSourceFile={uploadFlow.selectedSourceFile}
                    metadata={framePicker.metadata}
                    localVideoUrl={sourcePreviewUrl}
                    isUploading={uploadFlow.isUploading}
                    onVideoFile={uploadFlow.handleVideoFile}
                >
                    <VideoFramePicker
                        localVideoUrl={sourcePreviewUrl}
                        videoRef={framePicker.videoRef}
                        canvasRef={framePicker.canvasRef}
                        metadata={framePicker.metadata}
                        frameSecond={framePicker.frameSecond}
                        isUploading={uploadFlow.isUploading}
                        onLoadedMetadata={framePicker.loadMetadataFromVideo}
                        onFrameChange={framePicker.setFrame}
                        onUseSelectedFrame={captureCover}
                    />
                </VideoSourcePicker>

                <form className="moment-editor-form" onSubmit={(event) => event.preventDefault()}>
                    <VideoCoverPicker
                        coverAsset={uploadFlow.coverAsset}
                        localCoverUrl={uploadFlow.localCoverUrl}
                        isUploading={uploadFlow.isUploading}
                        onCoverFile={uploadFlow.handleCoverFile}
                    />

                    <label>
                        <span>Caption</span>
                        <textarea
                            value={caption}
                            maxLength={2200}
                            onChange={(event) => setCaption(event.target.value)}
                            rows={6}
                        />
                    </label>

                    <TagInput
                        tags={tags}
                        onChange={setTags}
                        onInputStateChange={setTagInputState}
                    />
                    {tagInputState.error ? <p className="moment-editor-error inline">{tagInputState.error}</p> : null}

                    <label>
                        <span>Visibility</span>
                        <select value={visibility} onChange={(event) => setVisibility(event.target.value)}>
                            <option value="private">Private</option>
                            <option value="public">Public</option>
                        </select>
                    </label>

                    <div className="moment-editor-actions">
                        <button
                            type="button"
                            onClick={() => { void saveMoment("draft"); }}
                            disabled={!canSave}
                        >
                            {isSaving ? "Saving..." : "Save draft"}
                        </button>
                        <button
                            type="button"
                            className="primary"
                            onClick={() => { void saveMoment("published"); }}
                            disabled={!canSave}
                        >
                            {isSaving ? "Publishing..." : "Publish"}
                        </button>
                    </div>
                </form>
            </section>
        </main>
    );
}

function MomentProcessingSummary({ moment, metadata }) {
    const width = metadata?.width || moment?.width || 0;
    const height = metadata?.height || moment?.height || 0;
    const duration = metadata?.duration || moment?.duration_seconds || 0;
    const orientation = metadata?.orientation || moment?.orientation || deriveOrientation(width, height);

    return (
        <section className="moment-processing-summary" aria-label="Moment processing status">
            <span>Processing: {moment?.processing_status || "not started"}</span>
            <span>Status: {moment?.status || "draft"}</span>
            <span>Visibility: {moment?.visibility || "private"}</span>
            {duration ? <span>Duration: {formatDuration(duration)}</span> : null}
            {width && height ? <span>Resolution: {Math.round(width)}x{Math.round(height)}</span> : null}
            {orientation ? <span>Orientation: {orientation}</span> : null}
        </section>
    );
}

export default MomentEditor;
