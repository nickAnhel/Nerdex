import { useContext, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import "./VideoEditor.css";

import { StoreContext } from "../..";
import AssetService from "../../service/AssetService";
import VideoService from "../../service/VideoService";
import Loader from "../../components/loader/Loader";
import TagInput from "../../components/tag-input/TagInput";
import Unauthorized from "../../components/unauthorized/Unauthorized";
import { normalizeTagList } from "../../utils/tags";
import { formatDuration } from "../../components/video-card/VideoCard";


const DEFAULT_FORM = {
    title: "",
    description: "",
    visibility: "private",
    status: "draft",
    publishRequestedAt: null,
    tags: [],
    chapters: [],
};

const INITIAL_ASSET_UPLOAD_STATES = {
    source: "idle",
    cover: "idle",
};

const ASSET_STATUS_LABELS = {
    pending_upload: "Waiting for upload",
    uploaded: "Uploaded",
    processing: "Processing",
    ready: "Ready",
    failed: "Failed",
    deleted: "Deleted",
};

function formatStatusLabel(status) {
    return ASSET_STATUS_LABELS[status] || status || "Not uploaded";
}

function getReadyVariantCount(asset) {
    return asset?.variants?.filter((variant) => variant.status === "ready").length || 0;
}

function VideoEditor() {
    const { store } = useContext(StoreContext);
    const navigate = useNavigate();
    const { videoId } = useParams();
    const videoRef = useRef(null);
    const canvasRef = useRef(null);

    const [form, setForm] = useState(DEFAULT_FORM);
    const [sourceAsset, setSourceAsset] = useState(null);
    const [coverAsset, setCoverAsset] = useState(null);
    const [localVideoUrl, setLocalVideoUrl] = useState("");
    const [localCoverUrl, setLocalCoverUrl] = useState("");
    const [metadata, setMetadata] = useState(null);
    const [frameSecond, setFrameSecond] = useState(0);
    const [isLoading, setIsLoading] = useState(Boolean(videoId));
    const [isSaving, setIsSaving] = useState(false);
    const [isUploading, setIsUploading] = useState(false);
    const [assetUploadStates, setAssetUploadStates] = useState(INITIAL_ASSET_UPLOAD_STATES);
    const [publishAttempted, setPublishAttempted] = useState(false);
    const [publishNotice, setPublishNotice] = useState("");
    const [error, setError] = useState("");
    const [tagInputState, setTagInputState] = useState({ error: "" });

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
                setForm({
                    title: video.title || "",
                    description: video.description || "",
                    visibility: video.visibility || "private",
                    status: video.status || "draft",
                    publishRequestedAt: video.publish_requested_at || null,
                    tags: normalizeTagList(video.tags),
                    chapters: video.chapters || [],
                });
                setSourceAsset(video.source_asset || null);
                setCoverAsset(video.cover || null);
                setLocalCoverUrl(video.cover?.preview_url || video.cover?.original_url || "");
                setMetadata({
                    duration: video.duration_seconds || 0,
                    width: video.source_asset?.width || video.cover?.width || 0,
                    height: video.source_asset?.height || video.cover?.height || 0,
                });
            } catch (fetchError) {
                setError(fetchError?.response?.data?.detail || "Failed to load video editor.");
            } finally {
                setIsLoading(false);
            }
        };
        void fetchEditor();
    }, [videoId]);

    useEffect(() => {
        if (!videoId || !form.publishRequestedAt || form.status === "published") {
            return undefined;
        }

        const intervalId = window.setInterval(async () => {
            try {
                const res = await VideoService.getVideoEditor(videoId);
                const video = res.data;
                setSourceAsset(video.source_asset || null);
                setCoverAsset(video.cover || null);
                setLocalCoverUrl(video.cover?.preview_url || video.cover?.original_url || "");
                setForm((prevForm) => ({
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
    }, [videoId, form.publishRequestedAt, form.status]);

    useEffect(() => () => {
        if (localVideoUrl) {
            URL.revokeObjectURL(localVideoUrl);
        }
        if (localCoverUrl && localCoverUrl.startsWith("blob:")) {
            URL.revokeObjectURL(localCoverUrl);
        }
    }, [localVideoUrl, localCoverUrl]);

    const canSave = useMemo(() => (
        Boolean(sourceAsset?.asset_id && coverAsset?.asset_id)
        && !isSaving
        && !isUploading
        && assetUploadStates.source !== "uploading"
        && assetUploadStates.cover !== "uploading"
        && !tagInputState.error
    ), [sourceAsset, coverAsset, isSaving, isUploading, assetUploadStates, tagInputState.error]);

    const showPublishAssetStatuses = publishAttempted || Boolean(form.publishRequestedAt);

    if (!store.isAuthenticated) {
        return <Unauthorized />;
    }

    if (isLoading) {
        return <div className="video-editor-state"><Loader /></div>;
    }

    const uploadAssetFile = async (file, assetType, usageContext) => {
        const initRes = await AssetService.initUpload({
            filename: file.name,
            size_bytes: file.size,
            declared_mime_type: file.type || null,
            asset_type: assetType,
            usage_context: usageContext,
        });
        const uploadRes = await AssetService.uploadFile(
            initRes.data.upload_url,
            file,
            initRes.data.upload_headers,
        );
        if (!uploadRes.ok) {
            throw new Error(await uploadRes.text() || "Upload failed.");
        }
        const finalizeRes = await AssetService.finalizeUpload(initRes.data.asset.asset_id);
        return finalizeRes.data.asset;
    };

    const handleVideoFile = async (file) => {
        if (!file) {
            return;
        }
        setError("");
        setPublishNotice("");
        setIsUploading(true);
        setAssetUploadStates((prevStates) => ({ ...prevStates, source: "uploading" }));
        try {
            const objectUrl = URL.createObjectURL(file);
            setLocalVideoUrl(objectUrl);
            const asset = await uploadAssetFile(file, "video", "video_source");
            setSourceAsset(asset);
            setAssetUploadStates((prevStates) => ({ ...prevStates, source: "ready" }));
        } catch (uploadError) {
            setError(uploadError?.response?.data?.detail || uploadError.message || "Failed to upload video.");
            setAssetUploadStates((prevStates) => ({ ...prevStates, source: "error" }));
        } finally {
            setIsUploading(false);
        }
    };

    const handleLoadedMetadata = () => {
        const node = videoRef.current;
        if (!node) {
            return;
        }
        setMetadata({
            duration: node.duration || 0,
            width: node.videoWidth || 0,
            height: node.videoHeight || 0,
        });
        setFrameSecond(Math.min(1, node.duration || 0));
    };

    const handleFrameChange = (event) => {
        const nextSecond = Number(event.target.value);
        setFrameSecond(nextSecond);
        if (videoRef.current) {
            videoRef.current.currentTime = nextSecond;
        }
    };

    const captureCover = async () => {
        const videoNode = videoRef.current;
        const canvasNode = canvasRef.current;
        if (!videoNode || !canvasNode) {
            return;
        }
        canvasNode.width = videoNode.videoWidth || 1280;
        canvasNode.height = videoNode.videoHeight || 720;
        const context = canvasNode.getContext("2d");
        context.drawImage(videoNode, 0, 0, canvasNode.width, canvasNode.height);
        const blob = await new Promise((resolve) => canvasNode.toBlob(resolve, "image/webp", 0.92));
        if (!blob) {
            setError("Failed to capture cover frame.");
            return;
        }
        const file = new File([blob], "video-cover.webp", { type: "image/webp" });
        await handleCoverFile(file, URL.createObjectURL(blob));
    };

    const handleCoverFile = async (file, previewUrl = null) => {
        if (!file) {
            return;
        }
        if (!file.type?.startsWith("image/")) {
            setError("Cover must be an image file.");
            return;
        }
        setIsUploading(true);
        setAssetUploadStates((prevStates) => ({ ...prevStates, cover: "uploading" }));
        setError("");
        setPublishNotice("");
        try {
            const asset = await uploadAssetFile(file, "image", "video_cover");
            setCoverAsset(asset);
            if (localCoverUrl && localCoverUrl.startsWith("blob:")) {
                URL.revokeObjectURL(localCoverUrl);
            }
            setLocalCoverUrl(previewUrl || URL.createObjectURL(file));
            setAssetUploadStates((prevStates) => ({ ...prevStates, cover: "ready" }));
        } catch (uploadError) {
            setError(uploadError?.response?.data?.detail || uploadError.message || "Failed to upload cover.");
            setAssetUploadStates((prevStates) => ({ ...prevStates, cover: "error" }));
            if (previewUrl?.startsWith("blob:")) {
                URL.revokeObjectURL(previewUrl);
            }
        } finally {
            setIsUploading(false);
        }
    };

    const persistVideo = async ({ publish = false } = {}) => {
        if (!canSave) {
            setError(tagInputState.error || "Upload a video source and cover before saving.");
            return;
        }
        if (publish) {
            setPublishAttempted(true);
        }
        const payload = {
            source_asset_id: sourceAsset.asset_id,
            cover_asset_id: coverAsset.asset_id,
            title: form.title,
            description: form.description,
            visibility: form.visibility,
            status: publish ? "published" : form.status,
            tags: form.tags,
            chapters: form.chapters,
        };
        setIsSaving(true);
        setError("");
        try {
            const res = videoId
                ? await VideoService.updateVideo(videoId, payload)
                : await VideoService.createVideo(payload);
            const saved = res.data;
            store.refreshPosts();
            setSourceAsset(saved.source_asset || sourceAsset);
            setCoverAsset(saved.cover || coverAsset);
            setForm((prevForm) => ({
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
            }
        } catch (saveError) {
            setError(saveError?.response?.data?.detail || "Failed to save video.");
        } finally {
            setIsSaving(false);
        }
    };

    const addChapter = () => {
        setForm((prevForm) => ({
            ...prevForm,
            chapters: [...prevForm.chapters, { title: "", startsAtSeconds: 0 }],
        }));
    };

    const updateChapter = (index, patch) => {
        setForm((prevForm) => ({
            ...prevForm,
            chapters: prevForm.chapters.map((chapter, currentIndex) => (
                currentIndex === index ? { ...chapter, ...patch } : chapter
            )),
        }));
    };

    const removeChapter = (index) => {
        setForm((prevForm) => ({
            ...prevForm,
            chapters: prevForm.chapters.filter((_, currentIndex) => currentIndex !== index),
        }));
    };

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

            {
                error &&
                <p className="video-editor-error">{error}</p>
            }

            {
                publishNotice &&
                <p className="video-editor-notice">{publishNotice}</p>
            }

            {
                showPublishAssetStatuses &&
                <section className="video-asset-status-panel" aria-label="Video asset upload statuses">
                    <AssetStatusItem
                        label="Video file"
                        asset={sourceAsset}
                        uploadState={assetUploadStates.source}
                    />
                    <AssetStatusItem
                        label="Cover image"
                        asset={coverAsset}
                        uploadState={assetUploadStates.cover}
                    />
                </section>
            }

            <section className="video-editor-grid">
                <div className="video-editor-panel">
                    <label>
                        Video source
                        <input
                            type="file"
                            accept="video/mp4,video/webm,video/quicktime,.mp4,.webm,.mov"
                            onChange={(event) => handleVideoFile(event.target.files?.[0])}
                            disabled={isUploading}
                        />
                    </label>

                    {
                        localVideoUrl &&
                        <div className="video-frame-picker">
                            <video
                                ref={videoRef}
                                src={localVideoUrl}
                                preload="metadata"
                                controls
                                onLoadedMetadata={handleLoadedMetadata}
                            />
                            {
                                metadata?.duration > 0 &&
                                <>
                                    <label>
                                        Cover frame {formatDuration(frameSecond)}
                                        <input
                                            type="range"
                                            min="0"
                                            max={metadata.duration}
                                            step="0.1"
                                            value={frameSecond}
                                            onChange={handleFrameChange}
                                        />
                                    </label>
                                    <button type="button" onClick={captureCover} disabled={isUploading}>
                                        Capture cover
                                    </button>
                                </>
                            }
                        </div>
                    }

                    <label>
                        Cover image
                        <input
                            type="file"
                            accept="image/jpeg,image/png,image/webp,image/gif,.jpg,.jpeg,.png,.webp,.gif"
                            onChange={(event) => handleCoverFile(event.target.files?.[0])}
                            disabled={isUploading}
                        />
                    </label>

                    {
                        metadata &&
                        <div className="video-editor-metadata">
                            <span>{Math.round(metadata.width)}x{Math.round(metadata.height)}</span>
                            <span>{formatDuration(metadata.duration)}</span>
                        </div>
                    }

                    {
                        localCoverUrl &&
                        <div className="video-cover-preview">
                            <img src={localCoverUrl} alt="Selected video cover" />
                        </div>
                    }
                    <canvas ref={canvasRef} hidden />
                </div>

                <div className="video-editor-panel">
                    <label>
                        Title
                        <input
                            type="text"
                            value={form.title}
                            maxLength={300}
                            onChange={(event) => setForm((prevForm) => ({ ...prevForm, title: event.target.value }))}
                            placeholder="Video title"
                        />
                    </label>
                    <label>
                        Description
                        <textarea
                            value={form.description}
                            maxLength={4000}
                            onChange={(event) => setForm((prevForm) => ({ ...prevForm, description: event.target.value }))}
                            placeholder="Describe the video"
                        />
                    </label>
                    <label>
                        Visibility
                        <select
                            value={form.visibility}
                            onChange={(event) => setForm((prevForm) => ({ ...prevForm, visibility: event.target.value }))}
                        >
                            <option value="private">Private</option>
                            <option value="public">Public</option>
                        </select>
                    </label>

                    <TagInput
                        tags={form.tags}
                        onChange={(tags) => setForm((prevForm) => ({ ...prevForm, tags }))}
                        onInputStateChange={setTagInputState}
                    />

                    <div className="video-chapters">
                        <div className="video-chapters-header">
                            <h2>Chapters</h2>
                            <button type="button" onClick={addChapter}>Add chapter</button>
                        </div>
                        {
                            form.chapters.map((chapter, index) => (
                                <div className="video-chapter-row" key={`${index}-${chapter.startsAtSeconds}`}>
                                    <input
                                        type="text"
                                        value={chapter.title}
                                        maxLength={120}
                                        onChange={(event) => updateChapter(index, { title: event.target.value })}
                                        placeholder="Chapter title"
                                    />
                                    <input
                                        type="number"
                                        min="0"
                                        value={chapter.startsAtSeconds}
                                        onChange={(event) => updateChapter(index, { startsAtSeconds: Number(event.target.value) })}
                                    />
                                    <button type="button" onClick={() => removeChapter(index)}>Remove</button>
                                </div>
                            ))
                        }
                    </div>
                </div>
            </section>
        </main>
    );
}

function AssetStatusItem({ label, asset, uploadState }) {
    const effectiveStatus = ["uploading", "error"].includes(uploadState) ? uploadState : asset?.status;
    const readyVariantCount = getReadyVariantCount(asset);
    const statusClassName = `video-asset-status-value ${effectiveStatus || "missing"}`;

    return (
        <div className="video-asset-status-item">
            <div>
                <strong>{label}</strong>
                <span>{asset?.original_filename || "No file selected"}</span>
            </div>
            <div className="video-asset-status-meta">
                <span className={statusClassName}>
                    {effectiveStatus === "uploading" ? "Uploading" : formatStatusLabel(effectiveStatus)}
                </span>
                {
                    asset &&
                    <span>{readyVariantCount}/{asset.variants?.length || 0} variants ready</span>
                }
            </div>
        </div>
    );
}

export default VideoEditor;
