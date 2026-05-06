import { useEffect, useMemo, useState } from "react";

import AssetService from "../../../service/AssetService";


const MAX_VIDEO_SIZE_BYTES = 250 * 1024 * 1024;
const VIDEO_TYPES = new Set(["video/mp4", "video/webm", "video/quicktime", "video/x-quicktime"]);
const VIDEO_EXTENSIONS = new Set(["mp4", "webm", "mov"]);

const INITIAL_UPLOAD_STATES = {
    source: "empty",
    cover: "empty",
};

function extensionOf(filename = "") {
    return filename.includes(".") ? filename.split(".").pop().toLowerCase() : "";
}

function objectUrl(file) {
    return URL.createObjectURL(file);
}

export default function useVideoUploadFlow({ onSourceReplaced } = {}) {
    const [sourceAsset, setSourceAsset] = useState(null);
    const [coverAsset, setCoverAsset] = useState(null);
    const [localVideoUrl, setLocalVideoUrl] = useState("");
    const [localCoverUrl, setLocalCoverUrl] = useState("");
    const [selectedSourceFile, setSelectedSourceFile] = useState(null);
    const [selectedCoverFile, setSelectedCoverFile] = useState(null);
    const [assetUploadStates, setAssetUploadStates] = useState(INITIAL_UPLOAD_STATES);
    const [isUploading, setIsUploading] = useState(false);
    const [uploadError, setUploadError] = useState("");
    const [notice, setNotice] = useState("");

    useEffect(() => () => {
        if (localVideoUrl?.startsWith("blob:")) {
            URL.revokeObjectURL(localVideoUrl);
        }
        if (localCoverUrl?.startsWith("blob:")) {
            URL.revokeObjectURL(localCoverUrl);
        }
    }, [localCoverUrl, localVideoUrl]);

    const loadAssets = ({ source, cover }) => {
        setSourceAsset(source || null);
        setCoverAsset(cover || null);
        setLocalCoverUrl(cover?.preview_url || cover?.original_url || "");
        setAssetUploadStates({
            source: source ? source.status || "uploaded" : "empty",
            cover: cover ? cover.status || "uploaded" : "empty",
        });
    };

    const resetCover = () => {
        setCoverAsset(null);
        setSelectedCoverFile(null);
        if (localCoverUrl?.startsWith("blob:")) {
            URL.revokeObjectURL(localCoverUrl);
        }
        setLocalCoverUrl("");
        setAssetUploadStates((prevStates) => ({ ...prevStates, cover: "empty" }));
    };

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

    const validateVideoFile = (file) => {
        if (file.size > MAX_VIDEO_SIZE_BYTES) {
            return "Video source exceeds 250 MB.";
        }
        const extension = extensionOf(file.name);
        if (!VIDEO_TYPES.has(file.type) && !VIDEO_EXTENSIONS.has(extension)) {
            return "Video source format must be mp4, webm, or mov.";
        }
        return "";
    };

    const handleVideoFile = async (file) => {
        if (!file) {
            return;
        }
        const validationError = validateVideoFile(file);
        if (validationError) {
            setUploadError(validationError);
            setAssetUploadStates((prevStates) => ({ ...prevStates, source: "failed" }));
            return;
        }

        setUploadError("");
        setNotice("");
        setIsUploading(true);
        setSelectedSourceFile(file);
        setAssetUploadStates((prevStates) => ({ ...prevStates, source: "uploading" }));
        const nextUrl = objectUrl(file);
        if (localVideoUrl?.startsWith("blob:")) {
            URL.revokeObjectURL(localVideoUrl);
        }
        setLocalVideoUrl(nextUrl);
        resetCover();
        onSourceReplaced?.();

        try {
            const asset = await uploadAssetFile(file, "video", "video_source");
            setSourceAsset(asset);
            setAssetUploadStates((prevStates) => ({ ...prevStates, source: asset.status || "uploaded" }));
            setNotice("Video source selected. Choose a new cover before saving.");
        } catch (error) {
            setUploadError(error?.response?.data?.detail || error.message || "Failed to upload video.");
            setAssetUploadStates((prevStates) => ({ ...prevStates, source: "failed" }));
        } finally {
            setIsUploading(false);
        }
    };

    const handleCoverFile = async (file, previewUrl = null) => {
        if (!file) {
            return;
        }
        if (!file.type?.startsWith("image/")) {
            setUploadError("Cover must be an image file.");
            return;
        }
        setUploadError("");
        setNotice("");
        setIsUploading(true);
        setSelectedCoverFile(file);
        setAssetUploadStates((prevStates) => ({ ...prevStates, cover: "uploading" }));

        try {
            const asset = await uploadAssetFile(file, "image", "video_cover");
            setCoverAsset(asset);
            if (localCoverUrl?.startsWith("blob:")) {
                URL.revokeObjectURL(localCoverUrl);
            }
            setLocalCoverUrl(previewUrl || objectUrl(file));
            setAssetUploadStates((prevStates) => ({ ...prevStates, cover: asset.status || "uploaded" }));
        } catch (error) {
            setUploadError(error?.response?.data?.detail || error.message || "Failed to upload cover.");
            setAssetUploadStates((prevStates) => ({ ...prevStates, cover: "failed" }));
            if (previewUrl?.startsWith("blob:")) {
                URL.revokeObjectURL(previewUrl);
            }
        } finally {
            setIsUploading(false);
        }
    };

    const canUseAssets = useMemo(() => (
        Boolean(sourceAsset?.asset_id && coverAsset?.asset_id)
        && !isUploading
        && assetUploadStates.source !== "uploading"
        && assetUploadStates.cover !== "uploading"
    ), [assetUploadStates, coverAsset, isUploading, sourceAsset]);

    return {
        sourceAsset,
        coverAsset,
        localVideoUrl,
        localCoverUrl,
        selectedSourceFile,
        selectedCoverFile,
        assetUploadStates,
        isUploading,
        uploadError,
        notice,
        canUseAssets,
        loadAssets,
        handleVideoFile,
        handleCoverFile,
        setSourceAsset,
        setCoverAsset,
    };
}
