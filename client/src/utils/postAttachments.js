export function resolveAssetTypeForFile(file) {
    const mimeType = (file?.type || "").toLowerCase();
    if (mimeType.startsWith("image/")) {
        return "image";
    }
    if (mimeType.startsWith("video/")) {
        return "video";
    }
    return "file";
}

export function formatAttachmentSize(sizeBytes) {
    if (!Number.isFinite(sizeBytes) || sizeBytes <= 0) {
        return "";
    }

    const units = ["B", "KB", "MB", "GB"];
    let value = sizeBytes;
    let unitIndex = 0;

    while (value >= 1024 && unitIndex < units.length - 1) {
        value /= 1024;
        unitIndex += 1;
    }

    const rounded = value >= 10 || unitIndex === 0
        ? Math.round(value)
        : Number(value.toFixed(1));

    return `${rounded} ${units[unitIndex]}`;
}

export function serializePostAttachments(mediaAttachments, fileAttachments) {
    const serialize = (attachments, attachmentType) => (
        attachments
            .filter((attachment) => attachment.uploadState === "ready" && attachment.asset_id)
            .map((attachment, index) => ({
                asset_id: attachment.asset_id,
                attachment_type: attachmentType,
                position: index,
            }))
    );

    return [
        ...serialize(mediaAttachments, "media"),
        ...serialize(fileAttachments, "file"),
    ];
}

export function normalizePostAttachment(attachment) {
    return {
        id: `asset-${attachment.asset_id}`,
        asset_id: attachment.asset_id,
        attachment_type: attachment.attachment_type,
        asset_type: attachment.asset_type,
        mime_type: attachment.mime_type,
        file_kind: attachment.file_kind || "file",
        original_filename: attachment.original_filename || "Untitled file",
        size_bytes: attachment.size_bytes,
        preview_url: attachment.preview_url,
        original_url: attachment.original_url,
        poster_url: attachment.poster_url,
        download_url: attachment.download_url,
        stream_url: attachment.stream_url,
        is_audio: Boolean(attachment.is_audio),
        duration_ms: attachment.duration_ms || null,
        uploadState: "ready",
        error: "",
    };
}

export function buildComposerAttachmentFromAsset(asset, attachmentType, fallbackName) {
    const variants = Array.isArray(asset?.variants) ? asset.variants : [];
    const originalVariant = variants.find((variant) => variant.asset_variant_type === "original");
    const previewVariant = asset.asset_type === "image"
        ? variants.find((variant) => variant.asset_variant_type === "image_small")
            || variants.find((variant) => variant.asset_variant_type === "image_medium")
            || originalVariant
        : variants.find((variant) => variant.asset_variant_type === "video_preview_small")
            || variants.find((variant) => variant.asset_variant_type === "video_preview_medium")
            || originalVariant;

    const mimeType = originalVariant?.mime_type || "";

    return {
        id: `asset-${asset.asset_id}`,
        asset_id: asset.asset_id,
        attachment_type: attachmentType,
        asset_type: asset.asset_type,
        mime_type: mimeType,
        file_kind: deriveFileKind(mimeType, asset.original_filename || fallbackName),
        original_filename: asset.original_filename || fallbackName || "Untitled file",
        size_bytes: asset.size_bytes,
        preview_url: previewVariant?.url || originalVariant?.url || null,
        original_url: originalVariant?.url || previewVariant?.url || null,
        poster_url: null,
        download_url: null,
        stream_url: originalVariant?.url || null,
        is_audio: mimeType.startsWith("audio/"),
        duration_ms: previewVariant?.duration_ms || originalVariant?.duration_ms || null,
        uploadState: "ready",
        error: "",
    };
}

export function deriveFileKind(mimeType, filename = "") {
    const normalizedMime = (mimeType || "").toLowerCase();
    const extension = filename.includes(".")
        ? filename.split(".").pop().toLowerCase()
        : "";

    if (normalizedMime.startsWith("image/")) {
        return "image";
    }
    if (normalizedMime.startsWith("video/")) {
        return "video";
    }
    if (normalizedMime.startsWith("audio/")) {
        return "audio";
    }
    if (normalizedMime === "application/pdf" || extension === "pdf") {
        return "pdf";
    }
    if (
        ["application/msword", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"].includes(normalizedMime)
        || ["doc", "docx"].includes(extension)
    ) {
        return "doc";
    }
    if (
        [
            "application/vnd.ms-excel",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "text/csv",
        ].includes(normalizedMime)
        || ["xls", "xlsx", "csv"].includes(extension)
    ) {
        return "sheet";
    }
    if (
        [
            "application/vnd.ms-powerpoint",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ].includes(normalizedMime)
        || ["ppt", "pptx"].includes(extension)
    ) {
        return "slides";
    }
    if (normalizedMime.startsWith("text/") || ["txt", "md"].includes(extension)) {
        return "text";
    }
    if (
        ["application/zip", "application/x-rar-compressed", "application/x-7z-compressed"].includes(normalizedMime)
        || ["zip", "rar", "7z"].includes(extension)
    ) {
        return "archive";
    }
    return "file";
}
