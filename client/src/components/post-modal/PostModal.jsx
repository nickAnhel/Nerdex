import { useContext, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import "./PostModal.css";

import { StoreContext } from "../..";

import Modal from "../modal/Modal";
import Loader from "../loader/Loader";
import TagInput from "../tag-input/TagInput";
import AddIcon from "../icons/AddIcon";
import CloseIcon from "../icons/CloseIcon";
import FileTypeIcon from "../icons/FileTypeIcon";
import AssetService from "../../service/AssetService";
import {
    buildComposerAttachmentFromAsset,
    formatAttachmentSize,
    normalizePostAttachment,
    resolveAssetTypeForFile,
    serializePostAttachments,
} from "../../utils/postAttachments";
import { areTagListsEqual, dedupeTags, normalizeTagList } from "../../utils/tags";


const EMPTY_TAGS = [];
const EMPTY_ATTACHMENTS = [];
const POST_MEDIA_LIMIT = 30;
const POST_FILE_LIMIT = 10;


function moveItem(items, fromIndex, toIndex) {
    if (fromIndex === toIndex || fromIndex < 0 || toIndex < 0 || fromIndex >= items.length || toIndex >= items.length) {
        return items;
    }

    const nextItems = [...items];
    const [movedItem] = nextItems.splice(fromIndex, 1);
    nextItems.splice(toIndex, 0, movedItem);
    return nextItems;
}

function areAttachmentListsEqual(left, right) {
    if (left.length !== right.length) {
        return false;
    }

    return left.every((attachment, index) => (
        attachment.asset_id === right[index]?.asset_id
        && attachment.attachment_type === right[index]?.attachment_type
    ));
}

function PostModal({
    active,
    setActive,

    postId,
    content,
    status = "published",
    visibility = "public",
    tags = null,
    mediaAttachments = EMPTY_ATTACHMENTS,
    fileAttachments = EMPTY_ATTACHMENTS,
    savePostFunc,
    navigateTo,
    onSaved,

    modalHeader,
    buttonText,
}) {
    const { store } = useContext(StoreContext);

    const navigate = useNavigate();
    const mediaInputRef = useRef(null);
    const fileInputRef = useRef(null);
    const dragStateRef = useRef(null);

    const incomingTags = tags ?? EMPTY_TAGS;
    const normalizedIncomingTags = useMemo(
        () => normalizeTagList(incomingTags),
        [incomingTags]
    );
    const normalizedIncomingMedia = useMemo(
        () => (mediaAttachments || []).map(normalizePostAttachment),
        [mediaAttachments]
    );
    const normalizedIncomingFiles = useMemo(
        () => (fileAttachments || []).map(normalizePostAttachment),
        [fileAttachments]
    );

    const [postContent, setPostContent] = useState(content || "");
    const [postStatus, setPostStatus] = useState(status);
    const [postVisibility, setPostVisibility] = useState(visibility);
    const [postTags, setPostTags] = useState(normalizedIncomingTags);
    const [initialPostTags, setInitialPostTags] = useState(normalizedIncomingTags);
    const [composerMediaAttachments, setComposerMediaAttachments] = useState(normalizedIncomingMedia);
    const [composerFileAttachments, setComposerFileAttachments] = useState(normalizedIncomingFiles);
    const [initialSerializedAttachments, setInitialSerializedAttachments] = useState(
        serializePostAttachments(normalizedIncomingMedia, normalizedIncomingFiles)
    );
    const [tagInputState, setTagInputState] = useState({
        value: "",
        normalizedValue: "",
        error: "",
    });
    const [isLoadingSavePost, setIsLoadingSavePost] = useState(false);
    const [saveError, setSaveError] = useState("");
    const [mediaError, setMediaError] = useState("");
    const [filesError, setFilesError] = useState("");

    useEffect(() => {
        setPostContent(content || "");
        setPostStatus(status);
        setPostVisibility(visibility);
        setPostTags(normalizedIncomingTags);
        setInitialPostTags(normalizedIncomingTags);
        setComposerMediaAttachments(normalizedIncomingMedia);
        setComposerFileAttachments(normalizedIncomingFiles);
        setInitialSerializedAttachments(
            serializePostAttachments(normalizedIncomingMedia, normalizedIncomingFiles)
        );
        setTagInputState({
            value: "",
            normalizedValue: "",
            error: "",
        });
        setSaveError("");
        setMediaError("");
        setFilesError("");
    }, [
        active,
        content,
        status,
        visibility,
        normalizedIncomingTags,
        normalizedIncomingMedia,
        normalizedIncomingFiles,
    ]);

    const isUploadingAttachments = [...composerMediaAttachments, ...composerFileAttachments]
        .some((attachment) => attachment.uploadState === "uploading");
    const hasAttachmentErrors = [...composerMediaAttachments, ...composerFileAttachments]
        .some((attachment) => attachment.uploadState === "error");
    const hasMeaningfulContent = (
        postContent.trim().length > 0
        || composerMediaAttachments.length > 0
        || composerFileAttachments.length > 0
    );
    const mediaGridClassName = composerMediaAttachments.length <= 3
        ? "post-media-composer-grid compact"
        : "post-media-composer-grid dense";

    const updateAttachmentsByType = (attachmentType, updater) => {
        if (attachmentType === "media") {
            setComposerMediaAttachments(updater);
            return;
        }
        setComposerFileAttachments(updater);
    };

    const handleRemoveAttachment = (attachmentType, attachmentId) => {
        updateAttachmentsByType(attachmentType, (prevAttachments) => (
            prevAttachments.filter((attachment) => attachment.id !== attachmentId)
        ));
    };

    const handleAttachmentUpload = async (attachmentType, selectedFiles) => {
        const isMediaBlock = attachmentType === "media";
        const attachmentLimit = isMediaBlock ? POST_MEDIA_LIMIT : POST_FILE_LIMIT;
        const currentAttachments = isMediaBlock ? composerMediaAttachments : composerFileAttachments;
        const setError = isMediaBlock ? setMediaError : setFilesError;

        setError("");
        setSaveError("");

        const remainingSlots = attachmentLimit - currentAttachments.length;
        if (remainingSlots <= 0) {
            setError(`This block is limited to ${attachmentLimit} items.`);
            return;
        }

        const filesToUpload = selectedFiles.slice(0, remainingSlots);
        if (filesToUpload.length < selectedFiles.length) {
            setError(`Only the first ${remainingSlots} files were queued.`);
        }

        for (const file of filesToUpload) {
            const tempId = `temp-${attachmentType}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
            updateAttachmentsByType(attachmentType, (prevAttachments) => ([
                ...prevAttachments,
                {
                    id: tempId,
                    asset_id: null,
                    attachment_type: attachmentType,
                    asset_type: resolveAssetTypeForFile(file),
                    mime_type: file.type || "",
                    file_kind: "file",
                    original_filename: file.name,
                    size_bytes: file.size,
                    preview_url: null,
                    original_url: null,
                    poster_url: null,
                    download_url: null,
                    stream_url: null,
                    is_audio: (file.type || "").startsWith("audio/"),
                    duration_ms: null,
                    uploadState: "uploading",
                    error: "",
                },
            ]));

            try {
                const initRes = await AssetService.initUpload({
                    filename: file.name,
                    size_bytes: file.size,
                    declared_mime_type: file.type || null,
                    asset_type: resolveAssetTypeForFile(file),
                    usage_context: attachmentType === "media" ? "post_media" : "post_file",
                });
                const uploadRes = await AssetService.uploadFile(
                    initRes.data.upload_url,
                    file,
                    initRes.data.upload_headers,
                );
                if (!uploadRes.ok) {
                    const uploadErrorText = await uploadRes.text();
                    throw new Error(uploadErrorText || "Failed to upload attachment.");
                }

                const finalizeRes = await AssetService.finalizeUpload(initRes.data.asset.asset_id);
                const uploadedAttachment = buildComposerAttachmentFromAsset(
                    finalizeRes.data.asset,
                    attachmentType,
                    file.name,
                );

                updateAttachmentsByType(attachmentType, (prevAttachments) => prevAttachments.map((attachment) => (
                    attachment.id === tempId ? uploadedAttachment : attachment
                )));
            } catch (error) {
                updateAttachmentsByType(attachmentType, (prevAttachments) => prevAttachments.map((attachment) => (
                    attachment.id === tempId
                        ? {
                            ...attachment,
                            uploadState: "error",
                            error: error?.response?.data?.detail || error?.message || "Upload failed.",
                        }
                        : attachment
                )));
            }
        }
    };

    const handleDragStart = (attachmentType, index) => {
        dragStateRef.current = { attachmentType, index };
    };

    const handleDrop = (attachmentType, index) => {
        const dragState = dragStateRef.current;
        dragStateRef.current = null;

        if (!dragState || dragState.attachmentType !== attachmentType) {
            return;
        }

        updateAttachmentsByType(attachmentType, (prevAttachments) => moveItem(prevAttachments, dragState.index, index));
    };

    const handleSavePost = async (event) => {
        event.preventDefault();
        setSaveError("");

        if (tagInputState.error) {
            setSaveError(tagInputState.error);
            return;
        }
        if (!hasMeaningfulContent) {
            setSaveError("Post must contain at least text, media, or files.");
            return;
        }
        if (isUploadingAttachments) {
            setSaveError("Wait until attachment uploads finish.");
            return;
        }
        if (hasAttachmentErrors) {
            setSaveError("Remove failed attachments before saving.");
            return;
        }

        const nextTags = tagInputState.normalizedValue
            ? dedupeTags([...postTags, tagInputState.normalizedValue])
            : postTags;
        if (nextTags !== postTags) {
            setPostTags(nextTags);
        }

        const serializedAttachments = serializePostAttachments(
            composerMediaAttachments,
            composerFileAttachments,
        );

        setIsLoadingSavePost(true);

        try {
            const postData = {
                content: postContent,
                status: postStatus,
                visibility: postVisibility,
                attachments: serializedAttachments,
            };

            if (postId) {
                if (!areTagListsEqual(nextTags, initialPostTags)) {
                    postData.tags = nextTags;
                }
                if (areAttachmentListsEqual(serializedAttachments, initialSerializedAttachments)) {
                    delete postData.attachments;
                }
            } else if (nextTags.length > 0) {
                postData.tags = nextTags;
            }

            const res = postId
                ? await savePostFunc(postId, postData)
                : await savePostFunc(postData);
            const savedPost = res.data;

            if (onSaved) {
                onSaved(savedPost);
            }

            store.refreshPosts();
            setActive(false);

            if (navigateTo) {
                navigate(typeof navigateTo === "function" ? navigateTo(savedPost) : navigateTo);
            }
        } catch (error) {
            setSaveError(error?.response?.data?.detail || "Failed to save post");
        } finally {
            setIsLoadingSavePost(false);
        }
    };

    return (
        <Modal active={active} setActive={setActive}>
            <form id="create-post-form">
                <h1>{modalHeader}</h1>

                <div className="post-attachment-section">
                    <div className="post-section-header">
                        <span>Media</span>
                        <button type="button" className="post-block-trigger" onClick={() => mediaInputRef.current?.click()}>
                            <AddIcon />
                        </button>
                    </div>

                    <input
                        ref={mediaInputRef}
                        type="file"
                        className="post-hidden-input"
                        accept="image/*,video/*"
                        multiple
                        onChange={(event) => {
                            const selectedFiles = Array.from(event.target.files || []);
                            if (selectedFiles.length > 0) {
                                handleAttachmentUpload("media", selectedFiles);
                            }
                            event.target.value = "";
                        }}
                    />

                    <div className={mediaGridClassName}>
                        {composerMediaAttachments.map((attachment, index) => (
                            <div
                                key={attachment.id}
                                className={`post-media-composer-tile ${attachment.uploadState}`}
                                draggable
                                onDragStart={() => handleDragStart("media", index)}
                                onDragOver={(event) => event.preventDefault()}
                                onDrop={() => handleDrop("media", index)}
                            >
                                {attachment.preview_url || attachment.original_url ? (
                                    attachment.asset_type === "video" ? (
                                        <video
                                            src={attachment.preview_url || attachment.original_url}
                                            muted
                                            playsInline
                                            preload="metadata"
                                        />
                                    ) : (
                                        <img
                                            src={attachment.preview_url || attachment.original_url}
                                            alt={attachment.original_filename}
                                        />
                                    )
                                ) : (
                                    <div className="post-media-placeholder">
                                        <span>{attachment.original_filename}</span>
                                    </div>
                                )}

                                <span className="post-media-order-chip">{index + 1}</span>
                                {attachment.asset_type === "video" && (
                                    <span className="post-media-kind-chip">Video</span>
                                )}
                                {attachment.uploadState !== "ready" && (
                                    <span className="post-media-status-chip">
                                        {attachment.uploadState === "uploading" ? "Uploading" : "Error"}
                                    </span>
                                )}
                                <button
                                    type="button"
                                    className="post-attachment-remove"
                                    onClick={() => handleRemoveAttachment("media", attachment.id)}
                                    aria-label={`Remove ${attachment.original_filename || "media"}`}
                                >
                                    <CloseIcon />
                                </button>
                                {attachment.error && (
                                    <span className="post-attachment-inline-error">{attachment.error}</span>
                                )}
                            </div>
                        ))}

                        {composerMediaAttachments.length < POST_MEDIA_LIMIT && (
                            <button
                                type="button"
                                className="post-media-add-tile"
                                onClick={() => mediaInputRef.current?.click()}
                                aria-label="Add media"
                            >
                                <AddIcon />
                            </button>
                        )}
                    </div>
                    <p className="post-section-hint">{composerMediaAttachments.length} / {POST_MEDIA_LIMIT}</p>
                    {mediaError && <div className="post-save-error">{mediaError}</div>}
                </div>

                <div className="post-attachment-section">
                    <div className="post-section-header">
                        <span>Files</span>
                        <button type="button" className="post-block-trigger" onClick={() => fileInputRef.current?.click()}>
                            <AddIcon />
                        </button>
                    </div>

                    <input
                        ref={fileInputRef}
                        type="file"
                        className="post-hidden-input"
                        multiple
                        onChange={(event) => {
                            const selectedFiles = Array.from(event.target.files || []);
                            if (selectedFiles.length > 0) {
                                handleAttachmentUpload("file", selectedFiles);
                            }
                            event.target.value = "";
                        }}
                    />

                    <div className="post-file-composer-list">
                        {composerFileAttachments.map((attachment, index) => (
                            <div
                                key={attachment.id}
                                className={`post-file-composer-card ${attachment.uploadState}`}
                                draggable
                                onDragStart={() => handleDragStart("file", index)}
                                onDragOver={(event) => event.preventDefault()}
                                onDrop={() => handleDrop("file", index)}
                            >
                                <span className="post-file-handle">::</span>
                                <span className="post-file-card-icon" aria-hidden="true">
                                    <FileTypeIcon kind={attachment.file_kind} />
                                </span>
                                <span className="post-file-card-body">
                                    <span className="post-file-card-name">{attachment.original_filename}</span>
                                    <span className="post-file-card-meta">
                                        {[attachment.file_kind?.toUpperCase(), formatAttachmentSize(attachment.size_bytes)].filter(Boolean).join(" . ")}
                                    </span>
                                    {attachment.error && (
                                        <span className="post-attachment-inline-error">{attachment.error}</span>
                                    )}
                                </span>
                                <span className="post-file-card-order">#{index + 1}</span>
                                <button
                                    type="button"
                                    className="post-attachment-remove text"
                                    onClick={() => handleRemoveAttachment("file", attachment.id)}
                                    aria-label={`Remove ${attachment.original_filename || "file"}`}
                                >
                                    <CloseIcon />
                                </button>
                            </div>
                        ))}
                    </div>
                    <p className="post-section-hint">{composerFileAttachments.length} / {POST_FILE_LIMIT}</p>
                    {filesError && <div className="post-save-error">{filesError}</div>}
                </div>

                <div className="post-content-wrapper">
                    <textarea
                        className="post-content"
                        placeholder="Type something..."
                        value={postContent}
                        onChange={(event) => setPostContent(event.target.value)}
                        maxLength={2048}
                    />
                    <span className="post-content-length">{postContent.trim().length} / 2048</span>
                </div>

                <div className="post-settings">
                    <TagInput
                        tags={postTags}
                        onChange={(nextTags) => {
                            setPostTags(nextTags);
                            setSaveError("");
                        }}
                        onInputStateChange={setTagInputState}
                    />

                    <div className="post-setting-group">
                        <span>Status</span>
                        <div className="post-setting-toggle">
                            <button
                                type="button"
                                className={postStatus === "published" ? "active" : ""}
                                onClick={() => setPostStatus("published")}
                            >
                                Publish
                            </button>
                            <button
                                type="button"
                                className={postStatus === "draft" ? "active" : ""}
                                onClick={() => setPostStatus("draft")}
                            >
                                Draft
                            </button>
                        </div>
                    </div>

                    <div className="post-setting-group">
                        <span>Visibility</span>
                        <div className="post-setting-toggle">
                            <button
                                type="button"
                                className={postVisibility === "public" ? "active" : ""}
                                onClick={() => setPostVisibility("public")}
                            >
                                Public
                            </button>
                            <button
                                type="button"
                                className={postVisibility === "private" ? "active" : ""}
                                onClick={() => setPostVisibility("private")}
                            >
                                Private
                            </button>
                        </div>
                        {postStatus === "draft" && (
                            <p className="post-settings-hint">
                                Drafts are visible only to you until published.
                            </p>
                        )}
                    </div>
                </div>

                {saveError && <div className="post-save-error">{saveError}</div>}

                <button
                    className="btn btn-primary btn-block"
                    disabled={!hasMeaningfulContent || isUploadingAttachments || hasAttachmentErrors}
                    onClick={(event) => { handleSavePost(event); }}
                >
                    {isLoadingSavePost ? <Loader /> : buttonText}
                </button>
            </form>
        </Modal>
    );
}

export default PostModal;
