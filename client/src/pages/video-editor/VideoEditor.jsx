import { useContext, useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import "./VideoEditor.css";

import { StoreContext } from "../..";
import Loader from "../../components/loader/Loader";
import Unauthorized from "../../components/unauthorized/Unauthorized";
import VideoService from "../../service/VideoService";
import {
    VideoChaptersEditor,
    VideoCoverPicker,
    VideoFramePicker,
    VideoProcessingStatusPanel,
    VideoPublishSettings,
    VideoSourcePicker,
} from "./components/VideoEditorComponents";
import useVideoChapters from "./hooks/useVideoChapters";
import useVideoEditorForm from "./hooks/useVideoEditorForm";
import useVideoFramePicker from "./hooks/useVideoFramePicker";
import useVideoUploadFlow from "./hooks/useVideoUploadFlow";


function VideoEditor() {
    const { store } = useContext(StoreContext);
    const navigate = useNavigate();
    const { videoId } = useParams();
    const [isLoading, setIsLoading] = useState(Boolean(videoId));
    const [isSaving, setIsSaving] = useState(false);
    const [publishAttempted, setPublishAttempted] = useState(false);
    const [publishNotice, setPublishNotice] = useState("");
    const [error, setError] = useState("");

    const formState = useVideoEditorForm();
    const uploadFlow = useVideoUploadFlow({
        onSourceReplaced: () => {
            setPublishNotice("Video source changed. Choose a new cover before saving.");
        },
    });
    const framePicker = useVideoFramePicker({
        onCoverCaptured: uploadFlow.handleCoverFile,
    });
    const chapters = useVideoChapters({
        chapters: formState.form.chapters,
        setChapters: formState.setChapters,
        durationSeconds: framePicker.metadata?.duration || uploadFlow.sourceAsset?.duration_ms / 1000 || 0,
    });

    useEffect(() => {
        if (!videoId) {
            setIsLoading(false);
            return;
        }

        const fetchEditor = async () => {
            setIsLoading(true);
            try {
                const res = await VideoService.getVideoEditor(videoId);
                const video = res.data;
                formState.loadVideo(video);
                uploadFlow.loadAssets({
                    source: video.source_asset || null,
                    cover: video.cover || null,
                });
                framePicker.setMetadata({
                    duration: video.duration_seconds || 0,
                    width: video.source_asset?.width || video.cover?.width || 0,
                    height: video.source_asset?.height || video.cover?.height || 0,
                    orientation: video.orientation || null,
                });
            } catch (fetchError) {
                setError(fetchError?.response?.data?.detail || "Failed to load video editor.");
            } finally {
                setIsLoading(false);
            }
        };

        void fetchEditor();
    // The editor load effect should run only when the route target changes.
    // Hook objects intentionally keep local form/upload state outside this dependency list.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [videoId]);

    useEffect(() => {
        if (!videoId || !formState.form.publishRequestedAt || formState.form.status === "published") {
            return undefined;
        }

        const intervalId = window.setInterval(async () => {
            try {
                const res = await VideoService.getVideoEditor(videoId);
                const video = res.data;
                uploadFlow.loadAssets({
                    source: video.source_asset || null,
                    cover: video.cover || null,
                });
                formState.setForm((prevForm) => ({
                    ...prevForm,
                    status: video.status || prevForm.status,
                    publishRequestedAt: video.publish_requested_at || prevForm.publishRequestedAt,
                }));
                if (video.status === "published") {
                    setPublishNotice("Published.");
                }
            } catch (pollError) {
                setError(pollError?.response?.data?.detail || "Failed to refresh video processing status.");
            }
        }, 5000);

        return () => window.clearInterval(intervalId);
    }, [formState, uploadFlow, videoId]);

    const canSave = useMemo(() => (
        uploadFlow.canUseAssets
        && !isSaving
        && !formState.validationError
        && chapters.validationErrors.length === 0
    ), [chapters.validationErrors.length, formState.validationError, isSaving, uploadFlow.canUseAssets]);

    const showStatusPanel = publishAttempted || Boolean(formState.form.publishRequestedAt) || uploadFlow.sourceAsset || uploadFlow.coverAsset;

    const persistVideo = async ({ publish = false } = {}) => {
        if (!canSave) {
            setError(
                formState.validationError
                || chapters.validationErrors[0]
                || "Upload a video source and required cover before saving."
            );
            return;
        }
        if (publish && !formState.form.title.trim()) {
            setError("Title is required before publishing.");
            setPublishAttempted(true);
            return;
        }
        if (publish) {
            setPublishAttempted(true);
        }

        setIsSaving(true);
        setError("");
        setPublishNotice("");
        try {
            const payload = formState.buildPayload({
                sourceAsset: uploadFlow.sourceAsset,
                coverAsset: uploadFlow.coverAsset,
                publish,
            });
            const res = videoId
                ? await VideoService.updateVideo(videoId, payload)
                : await VideoService.createVideo(payload);
            const saved = res.data;
            store.refreshPosts();
            uploadFlow.loadAssets({
                source: saved.source_asset || uploadFlow.sourceAsset,
                cover: saved.cover || uploadFlow.coverAsset,
            });
            formState.setForm((prevForm) => ({
                ...prevForm,
                status: saved.status,
                publishRequestedAt: saved.publish_requested_at || null,
            }));
            if (publish && saved.status === "published") {
                navigate(saved.canonical_path);
            } else if (publish) {
                setPublishNotice("Publishing requested. The video will publish when processing finishes.");
                if (!videoId) {
                    navigate(`/videos/${saved.video_id}/edit`, { replace: true });
                }
            } else if (!videoId) {
                navigate(`/videos/${saved.video_id}/edit`, { replace: true });
            } else {
                setPublishNotice("Draft saved.");
            }
        } catch (saveError) {
            setError(saveError?.response?.data?.detail || "Failed to save video.");
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
        return <div className="video-editor-state"><Loader /></div>;
    }

    return (
        <main className="video-editor-page">
            <header className="video-editor-header">
                <div>
                    <h1>{videoId ? "Edit video" : "New video"}</h1>
                    <p>Upload a video source and cover before saving.</p>
                </div>
                <div className="video-editor-actions">
                    <button type="button" onClick={() => persistVideo()} disabled={!canSave}>
                        {isSaving ? "Saving..." : "Save draft"}
                    </button>
                    <button type="button" onClick={() => persistVideo({ publish: true })} disabled={!canSave}>
                        {isSaving ? "Publishing..." : "Publish"}
                    </button>
                </div>
            </header>

            {(error || uploadFlow.uploadError) ? <p className="video-editor-error">{error || uploadFlow.uploadError}</p> : null}
            {(publishNotice || uploadFlow.notice) ? <p className="video-editor-notice">{publishNotice || uploadFlow.notice}</p> : null}

            {
                showStatusPanel &&
                <VideoProcessingStatusPanel
                    sourceAsset={uploadFlow.sourceAsset}
                    coverAsset={uploadFlow.coverAsset}
                    assetUploadStates={uploadFlow.assetUploadStates}
                />
            }

            <section className="video-editor-grid">
                <VideoSourcePicker
                    sourceAsset={uploadFlow.sourceAsset}
                    selectedSourceFile={uploadFlow.selectedSourceFile}
                    metadata={framePicker.metadata}
                    localVideoUrl={uploadFlow.localVideoUrl}
                    isUploading={uploadFlow.isUploading}
                    onVideoFile={uploadFlow.handleVideoFile}
                >
                    <VideoFramePicker
                        localVideoUrl={uploadFlow.localVideoUrl}
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

                <VideoCoverPicker
                    coverAsset={uploadFlow.coverAsset}
                    localCoverUrl={uploadFlow.localCoverUrl}
                    isUploading={uploadFlow.isUploading}
                    onCoverFile={uploadFlow.handleCoverFile}
                />

                <VideoPublishSettings
                    form={formState.form}
                    updateField={formState.updateField}
                    tagInputState={formState.tagInputState}
                    setTagInputState={formState.setTagInputState}
                />

                <VideoChaptersEditor
                    chapters={chapters.chapters}
                    frameSecond={framePicker.frameSecond}
                    durationSeconds={framePicker.metadata?.duration || 0}
                    validationErrors={chapters.validationErrors}
                    onAddAtCurrentTime={chapters.addChapterAt}
                    onUpdateChapter={chapters.updateChapter}
                    onUpdateChapterTime={chapters.updateChapterTime}
                    onRemoveChapter={chapters.removeChapter}
                />
            </section>
        </main>
    );
}

export default VideoEditor;
