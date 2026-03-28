import { useContext, useEffect, useRef, useState } from "react";
import { observer } from "mobx-react-lite";
import { useNavigate } from "react-router-dom";

import "./ProfileForm.css";

import AssetService from "../../service/AssetService";
import UserService from "../../service/UserService";

import { StoreContext } from "../..";

import Loader from "../loader/Loader";
import Modal from "../modal/Modal";
import { getAvatarRenderKey, getAvatarUrl } from "../../utils/avatar";


const VIEWPORT_SIZE = 280;
const MAX_ZOOM = 10;


function clamp(value, min, max) {
    return Math.min(Math.max(value, min), max);
}

function getBaseScale(imageSize) {
    if (!imageSize) {
        return 1;
    }

    return Math.max(
        VIEWPORT_SIZE / imageSize.width,
        VIEWPORT_SIZE / imageSize.height,
    );
}

function getRenderedSize(imageSize, scale) {
    const factor = getBaseScale(imageSize) * scale;

    return {
        width: imageSize.width * factor,
        height: imageSize.height * factor,
        factor,
    };
}

function constrainOffset(offset, imageSize, scale) {
    if (!imageSize) {
        return offset;
    }

    const rendered = getRenderedSize(imageSize, scale);

    return {
        x: clamp(offset.x, VIEWPORT_SIZE - rendered.width, 0),
        y: clamp(offset.y, VIEWPORT_SIZE - rendered.height, 0),
    };
}

function buildCenteredOffset(imageSize, scale) {
    const rendered = getRenderedSize(imageSize, scale);

    return {
        x: (VIEWPORT_SIZE - rendered.width) / 2,
        y: (VIEWPORT_SIZE - rendered.height) / 2,
    };
}

function buildCropPayload(imageSize, scale, offset) {
    const { factor } = getRenderedSize(imageSize, scale);
    const cropSizePx = VIEWPORT_SIZE / factor;
    const minDimension = Math.min(imageSize.width, imageSize.height);

    return {
        x: clamp((-offset.x) / factor / imageSize.width, 0, 1),
        y: clamp((-offset.y) / factor / imageSize.height, 0, 1),
        size: clamp(cropSizePx / minDimension, 0, 1),
    };
}

function ProfileForm() {
    const { store } = useContext(StoreContext);

    const navigate = useNavigate();
    const dragStateRef = useRef(null);
    const fileInputRef = useRef(null);

    const [isLoadingSave, setIsLoadingSave] = useState(false);
    const [isLoadingDelete, setIsLoadingDelete] = useState(false);
    const [isSavingAvatar, setIsSavingAvatar] = useState(false);
    const [isDeletingAvatar, setIsDeletingAvatar] = useState(false);

    const [username, setUsername] = useState("");
    const [avatarError, setAvatarError] = useState("");
    const [isPhotoModalActive, setIsPhotoModalActive] = useState(false);
    const [avatarModalStep, setAvatarModalStep] = useState("pick");
    const [selectedFile, setSelectedFile] = useState(null);
    const [preview, setPreview] = useState();
    const [imageSize, setImageSize] = useState(null);
    const [cropScale, setCropScale] = useState(1);
    const [cropOffset, setCropOffset] = useState({ x: 0, y: 0 });

    const avatarSrc = getAvatarUrl(store.user, "medium");
    const avatarRenderKey = getAvatarRenderKey(store.user, "medium");
    const zoomFillPercent = MAX_ZOOM <= 1
        ? 0
        : clamp(((cropScale - 1) / (MAX_ZOOM - 1)) * 100, 0, 100);

    useEffect(() => {
        setUsername(store.user.username || "");
    }, [store.user.username]);

    useEffect(() => {
        if (!selectedFile) {
            setPreview(undefined);
            return;
        }

        const objectUrl = URL.createObjectURL(selectedFile);
        setPreview(objectUrl);

        return () => URL.revokeObjectURL(objectUrl);
    }, [selectedFile]);

    const resetAvatarModal = () => {
        setAvatarError("");
        setAvatarModalStep("pick");
        setSelectedFile(null);
        setImageSize(null);
        setCropScale(1);
        setCropOffset({ x: 0, y: 0 });
        if (fileInputRef.current) {
            fileInputRef.current.value = "";
        }
    };

    const closeAvatarModal = () => {
        if (isSavingAvatar || isDeletingAvatar) {
            return;
        }

        setIsPhotoModalActive(false);
        resetAvatarModal();
    };

    const finishAvatarModal = () => {
        setIsPhotoModalActive(false);
        resetAvatarModal();
    };

    const handleReset = (e) => {
        e.preventDefault();
        setUsername(store.user.username || "");
    };

    const handleSubmit = async (e) => {
        e.preventDefault();

        if (!/^[A-Za-z0-9._-]{1,32}$/.test(username)) {
            alert("Invalid username");
            return;
        }

        setIsLoadingSave(true);

        try {
            const res = await UserService.updateMe({ username: username.trim() });
            store.setUser(res.data);
            handleReset(e);
        } catch (error) {
            console.log(error);
            console.log(error?.response?.data?.detail);
        }

        setIsLoadingSave(false);
    };

    const handleLogout = () => {
        store.logout();
        navigate("/login");
    };

    const handleDelete = async () => {
        setIsLoadingDelete(true);

        try {
            await UserService.deleteMe();
            store.logout();
            navigate("/login");
        } catch (error) {
            console.log(error);
            console.log(error?.response?.data?.detail);
        }

        setIsLoadingDelete(false);
    };

    const handleSelectFile = (e) => {
        const nextFile = e.target.files?.[0];
        setAvatarError("");
        setAvatarModalStep("pick");
        setImageSize(null);

        if (!nextFile) {
            setSelectedFile(null);
            return;
        }

        setSelectedFile(nextFile);
        setAvatarModalStep("crop");
    };

    const handlePreviewLoad = (e) => {
        const nextImageSize = {
            width: e.currentTarget.naturalWidth,
            height: e.currentTarget.naturalHeight,
        };

        setImageSize(nextImageSize);
        setCropScale(1);
        setCropOffset(buildCenteredOffset(nextImageSize, 1));
    };

    const handleZoomChange = (e) => {
        if (!imageSize) {
            return;
        }

        const nextScale = clamp(Number(e.target.value), 1, MAX_ZOOM);
        const previousFactor = getRenderedSize(imageSize, cropScale).factor;
        const nextFactor = getRenderedSize(imageSize, nextScale).factor;
        const cropCenterX = (VIEWPORT_SIZE / 2 - cropOffset.x) / previousFactor;
        const cropCenterY = (VIEWPORT_SIZE / 2 - cropOffset.y) / previousFactor;
        const nextOffset = constrainOffset(
            {
                x: VIEWPORT_SIZE / 2 - cropCenterX * nextFactor,
                y: VIEWPORT_SIZE / 2 - cropCenterY * nextFactor,
            },
            imageSize,
            nextScale,
        );

        setCropScale(nextScale);
        setCropOffset(nextOffset);
    };

    const handlePointerDown = (e) => {
        if (!imageSize) {
            return;
        }

        dragStateRef.current = {
            x: e.clientX,
            y: e.clientY,
            offset: cropOffset,
        };

        e.currentTarget.setPointerCapture(e.pointerId);
    };

    const handlePointerMove = (e) => {
        if (!dragStateRef.current || !imageSize) {
            return;
        }

        const deltaX = e.clientX - dragStateRef.current.x;
        const deltaY = e.clientY - dragStateRef.current.y;

        setCropOffset(
            constrainOffset(
                {
                    x: dragStateRef.current.offset.x + deltaX,
                    y: dragStateRef.current.offset.y + deltaY,
                },
                imageSize,
                cropScale,
            ),
        );
    };

    const handlePointerUp = (e) => {
        dragStateRef.current = null;
        if (e.currentTarget.hasPointerCapture?.(e.pointerId)) {
            e.currentTarget.releasePointerCapture(e.pointerId);
        }
    };

    const handleSaveAvatar = async (e) => {
        e.preventDefault();

        if (!selectedFile || !imageSize) {
            return;
        }

        setAvatarError("");
        setIsSavingAvatar(true);

        try {
            const crop = buildCropPayload(imageSize, cropScale, cropOffset);
            const initRes = await AssetService.initUpload({
                filename: selectedFile.name,
                size_bytes: selectedFile.size,
                declared_mime_type: selectedFile.type || null,
                asset_type: "image",
                usage_context: "avatar",
            });
            const uploadRes = await AssetService.uploadFile(
                initRes.data.upload_url,
                selectedFile,
                initRes.data.upload_headers,
            );
            if (!uploadRes.ok) {
                const uploadErrorText = await uploadRes.text();
                throw new Error(uploadErrorText || "Failed to upload avatar source image.");
            }
            const finalizeRes = await AssetService.finalizeUpload(initRes.data.asset.asset_id);
            const res = await UserService.updateAvatar({
                asset_id: finalizeRes.data.asset.asset_id,
                crop,
            });
            store.setUser(res.data);
            finishAvatarModal();
        } catch (error) {
            setAvatarError(
                error?.response?.data?.detail
                || error?.message
                || "Failed to save avatar.",
            );
        } finally {
            setIsSavingAvatar(false);
        }
    };

    const handleDeleteAvatar = async (e) => {
        e.preventDefault();
        setAvatarError("");
        setIsDeletingAvatar(true);

        try {
            const res = await UserService.deleteAvatar();
            store.setUser(res.data);
            finishAvatarModal();
        } catch (error) {
            setAvatarError(error?.response?.data?.detail || "Failed to delete avatar.");
        } finally {
            setIsDeletingAvatar(false);
        }
    };

    return (
        <div className="profile-form">
            <form onSubmit={handleSubmit}>
                <div className="form-section">
                    <button
                        type="button"
                        className="avatar-trigger"
                        onClick={() => {
                            resetAvatarModal();
                            setIsPhotoModalActive(true);
                        }}
                    >
                        <img
                            key={avatarRenderKey}
                            src={avatarSrc}
                            onError={(e) => { e.currentTarget.src = "/assets/profile.svg"; }}
                            alt="Profile avatar"
                        />
                    </button>

                    <input
                        type="text"
                        placeholder="Username"
                        value={username}
                        onChange={(e) => setUsername(e.target.value)}
                        maxLength={32}
                        pattern="[A-Za-z0-9._-]{1,32}"
                        required
                    />

                    <button className="btn btn-primary" type="submit" disabled={isLoadingSave}>
                        {isLoadingSave ? <Loader /> : "Save"}
                    </button>

                    <button
                        type="reset"
                        className="reset btn btn-secondary"
                        onClick={handleReset}
                    >
                        Reset
                    </button>
                </div>

                <div className="form-section">
                    <h2>Actions</h2>
                    <button
                        type="button"
                        className="logout btn btn-secondary"
                        onClick={handleLogout}
                    >
                        Log Out
                    </button>
                    <button
                        type="button"
                        className="delete btn btn-danger"
                        onClick={handleDelete}
                        disabled={isLoadingDelete}
                    >
                        {isLoadingDelete ? <Loader /> : "Delete Account"}
                    </button>
                </div>
            </form>

            <Modal active={isPhotoModalActive} setActive={closeAvatarModal}>
                <form className="image-form">
                    {
                        avatarModalStep === "pick" && (
                            <>
                                <div className="avatar-preview-shell">
                                    <img
                                        src={preview || avatarSrc}
                                        alt="Avatar preview"
                                        onError={(e) => { e.currentTarget.src = "/assets/profile.svg"; }}
                                    />
                                </div>

                                <label className="avatar-file-picker" htmlFor="profile-photo-file">
                                    Choose image
                                    <input
                                        ref={fileInputRef}
                                        type="file"
                                        id="profile-photo-file"
                                        accept="image/png,image/jpeg,image/webp,image/gif"
                                        onChange={handleSelectFile}
                                    />
                                </label>
                            </>
                        )
                    }

                    {
                        avatarModalStep === "crop" && preview && (
                            <>
                                <div className="avatar-crop-toolbar">
                                    <label className="avatar-file-picker avatar-file-picker-secondary" htmlFor="profile-photo-file">
                                        Change image
                                        <input
                                            ref={fileInputRef}
                                            type="file"
                                            id="profile-photo-file"
                                            accept="image/png,image/jpeg,image/webp,image/gif"
                                            onChange={handleSelectFile}
                                        />
                                    </label>
                                </div>

                                <div
                                    className="avatar-crop-viewport"
                                    onPointerDown={handlePointerDown}
                                    onPointerMove={handlePointerMove}
                                    onPointerUp={handlePointerUp}
                                    onPointerCancel={handlePointerUp}
                                >
                                    <img
                                        src={preview}
                                        alt="Avatar crop source"
                                        className="avatar-crop-image"
                                        onLoad={handlePreviewLoad}
                                        draggable={false}
                                        style={{
                                            transform: `translate(${cropOffset.x}px, ${cropOffset.y}px)`,
                                            width: `${getRenderedSize(imageSize || { width: VIEWPORT_SIZE, height: VIEWPORT_SIZE }, cropScale).width}px`,
                                            height: `${getRenderedSize(imageSize || { width: VIEWPORT_SIZE, height: VIEWPORT_SIZE }, cropScale).height}px`,
                                        }}
                                    />
                                    <div className="avatar-crop-overlay" />
                                </div>

                                <label className="avatar-zoom-control">
                                    <span>Zoom {cropScale.toFixed(2)}x</span>
                                    <input
                                        className="avatar-zoom-slider"
                                        type="range"
                                        min="1"
                                        max={String(MAX_ZOOM)}
                                        step="0.01"
                                        value={cropScale}
                                        onChange={handleZoomChange}
                                        style={{ "--zoom-fill": `${zoomFillPercent}%` }}
                                    />
                                </label>

                                <button
                                    className="btn btn-primary"
                                    type="submit"
                                    onClick={handleSaveAvatar}
                                    disabled={isSavingAvatar || !selectedFile || !imageSize}
                                >
                                    {isSavingAvatar ? (
                                        <>
                                            <Loader />
                                            <span>Saving avatar...</span>
                                        </>
                                    ) : "Save avatar"}
                                </button>

                                <button
                                    type="button"
                                    className="reset btn btn-secondary"
                                    onClick={() => {
                                        if (!imageSize) {
                                            return;
                                        }
                                        setCropScale(1);
                                        setCropOffset(buildCenteredOffset(imageSize, 1));
                                    }}
                                >
                                    Reset crop
                                </button>
                            </>
                        )
                    }

                    <button
                        type="button"
                        className="delete btn btn-danger"
                        onClick={handleDeleteAvatar}
                        disabled={isDeletingAvatar || isSavingAvatar || !store.user.avatar_asset_id}
                    >
                        {isDeletingAvatar ? <Loader /> : "Delete avatar"}
                    </button>

                    {
                        avatarError &&
                        <p className="avatar-error">{avatarError}</p>
                    }
                </form>
            </Modal>
        </div>
    );
}


export default observer(ProfileForm);
