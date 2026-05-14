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

function isValidHttpUrl(value) {
    try {
        const url = new URL(value);
        return url.protocol === "http:" || url.protocol === "https:";
    } catch (_error) {
        return false;
    }
}

function normalizeLinksFromUser(userLinks) {
    if (!Array.isArray(userLinks) || userLinks.length === 0) {
        return [{ label: "", url: "" }];
    }

    return userLinks.map((link) => ({
        label: link.label || "",
        url: link.url || "",
    }));
}

function ProfileForm() {
    const { store } = useContext(StoreContext);

    const navigate = useNavigate();
    const dragStateRef = useRef(null);
    const fileInputRef = useRef(null);

    const [isLoadingSaveProfile, setIsLoadingSaveProfile] = useState(false);
    const [isLoadingDelete, setIsLoadingDelete] = useState(false);
    const [isSavingAvatar, setIsSavingAvatar] = useState(false);
    const [isDeletingAvatar, setIsDeletingAvatar] = useState(false);
    const [isChangingPassword, setIsChangingPassword] = useState(false);

    const [profileError, setProfileError] = useState("");
    const [profileSuccess, setProfileSuccess] = useState("");
    const [passwordError, setPasswordError] = useState("");
    const [passwordSuccess, setPasswordSuccess] = useState("");

    const [username, setUsername] = useState("");
    const [displayName, setDisplayName] = useState("");
    const [bio, setBio] = useState("");
    const [links, setLinks] = useState([{ label: "", url: "" }]);

    const [currentPassword, setCurrentPassword] = useState("");
    const [newPassword, setNewPassword] = useState("");
    const [confirmNewPassword, setConfirmNewPassword] = useState("");

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
        setDisplayName(store.user.display_name || "");
        setBio(store.user.bio || "");
        setLinks(normalizeLinksFromUser(store.user.links));
    }, [store.user.username, store.user.display_name, store.user.bio, store.user.links]);

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

    const handleResetProfile = (e) => {
        e.preventDefault();
        setProfileError("");
        setProfileSuccess("");
        setUsername(store.user.username || "");
        setDisplayName(store.user.display_name || "");
        setBio(store.user.bio || "");
        setLinks(normalizeLinksFromUser(store.user.links));
    };

    const setLinkField = (index, field, value) => {
        setLinks((prev) => prev.map((item, itemIndex) => {
            if (itemIndex !== index) {
                return item;
            }
            return {
                ...item,
                [field]: value,
            };
        }));
    };

    const addLinkRow = () => {
        setLinks((prev) => [...prev, { label: "", url: "" }]);
    };

    const removeLinkRow = (index) => {
        setLinks((prev) => prev.filter((_, itemIndex) => itemIndex !== index));
    };

    const buildLinksPayload = () => {
        const payload = [];
        for (const row of links) {
            const label = row.label.trim();
            const url = row.url.trim();

            if (!label && !url) {
                continue;
            }
            if (!label || !url) {
                throw new Error("Fill both label and URL for each link");
            }
            if (!isValidHttpUrl(url)) {
                throw new Error("Link URL must start with http:// or https://");
            }

            payload.push({ label, url });
        }
        return payload;
    };

    const handleSaveProfile = async (e) => {
        e.preventDefault();
        setProfileError("");
        setProfileSuccess("");

        if (!/^[A-Za-z0-9._-]{1,32}$/.test(username)) {
            setProfileError("Invalid username");
            return;
        }

        let linksPayload;
        try {
            linksPayload = buildLinksPayload();
        } catch (validationError) {
            setProfileError(validationError.message || "Invalid links");
            return;
        }

        setIsLoadingSaveProfile(true);

        try {
            const res = await UserService.updateProfile({
                username: username.trim(),
                display_name: displayName.trim() || null,
                bio: bio.trim() || null,
                links: linksPayload,
            });
            store.setUser(res.data);
            setProfileSuccess("Profile updated");
        } catch (error) {
            setProfileError(error?.response?.data?.detail || "Failed to update profile");
        } finally {
            setIsLoadingSaveProfile(false);
        }
    };

    const handleChangePassword = async (e) => {
        e.preventDefault();
        setPasswordError("");
        setPasswordSuccess("");

        if (newPassword !== confirmNewPassword) {
            setPasswordError("New password and confirmation do not match");
            return;
        }

        setIsChangingPassword(true);

        try {
            await UserService.changePassword({
                current_password: currentPassword,
                new_password: newPassword,
            });
            setCurrentPassword("");
            setNewPassword("");
            setConfirmNewPassword("");
            setPasswordSuccess("Password updated");
        } catch (error) {
            setPasswordError(error?.response?.data?.detail || "Failed to change password");
        } finally {
            setIsChangingPassword(false);
        }
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
            <section className="profile-card profile-avatar-card">
                <h2>Avatar</h2>
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
                    <span>Change avatar</span>
                </button>
            </section>

            <section className="profile-card">
                <h2>Public profile</h2>
                <form onSubmit={handleSaveProfile} className="profile-section-form">
                    <div className="profile-field-group">
                        <label htmlFor="profile-username" className="profile-field-label">Username</label>
                        <input
                            id="profile-username"
                            type="text"
                            placeholder="Username"
                            value={username}
                            onChange={(e) => setUsername(e.target.value)}
                            maxLength={32}
                            pattern="[A-Za-z0-9._-]{1,32}"
                            required
                        />
                    </div>

                    <div className="profile-field-group">
                        <label htmlFor="profile-display-name" className="profile-field-label">Display name</label>
                        <input
                            id="profile-display-name"
                            type="text"
                            placeholder="Display name"
                            value={displayName}
                            onChange={(e) => setDisplayName(e.target.value)}
                            maxLength={64}
                        />
                    </div>

                    <div className="profile-field-group">
                        <label htmlFor="profile-bio" className="profile-field-label">Bio</label>
                        <textarea
                            id="profile-bio"
                            className="profile-field-textarea"
                            placeholder="Tell people about yourself"
                            value={bio}
                            onChange={(e) => setBio(e.target.value)}
                            maxLength={500}
                        />
                    </div>

                    <div className="profile-field-group">
                        <label className="profile-field-label">Links</label>
                        <div className="profile-links-block">
                        {links.map((link, index) => (
                            <div className="profile-link-row" key={`profile-link-${index}`}>
                                <input
                                    type="text"
                                    placeholder="Label"
                                    value={link.label}
                                    maxLength={32}
                                    onChange={(e) => setLinkField(index, "label", e.target.value)}
                                />
                                <input
                                    type="url"
                                    placeholder="https://example.com"
                                    value={link.url}
                                    onChange={(e) => setLinkField(index, "url", e.target.value)}
                                />
                                <button
                                    type="button"
                                    className="btn btn-outline-primary profile-link-remove"
                                    onClick={() => removeLinkRow(index)}
                                    disabled={links.length === 1}
                                >
                                    Remove
                                </button>
                            </div>
                        ))}
                        <button
                            type="button"
                            className="btn btn-outline-primary profile-link-add"
                            onClick={addLinkRow}
                        >
                            Add link
                        </button>
                        </div>
                    </div>

                    {profileError ? <div className="profile-error">{profileError}</div> : null}
                    {profileSuccess ? <div className="profile-success">{profileSuccess}</div> : null}

                    <div className="profile-form-actions">
                        <button className="btn btn-primary" type="submit" disabled={isLoadingSaveProfile}>
                            {isLoadingSaveProfile ? <Loader /> : "Save profile"}
                        </button>

                        <button
                            type="reset"
                            className="reset btn btn-secondary"
                            onClick={handleResetProfile}
                            disabled={isLoadingSaveProfile}
                        >
                            Reset
                        </button>
                    </div>
                </form>
            </section>

            <section className="profile-card">
                <h2>Password</h2>
                <form onSubmit={handleChangePassword} className="profile-section-form">
                    <input
                        type="password"
                        placeholder="Current password"
                        value={currentPassword}
                        onChange={(e) => setCurrentPassword(e.target.value)}
                        minLength={1}
                        required
                    />
                    <input
                        type="password"
                        placeholder="New password"
                        value={newPassword}
                        onChange={(e) => setNewPassword(e.target.value)}
                        minLength={8}
                        required
                    />
                    <input
                        type="password"
                        placeholder="Confirm new password"
                        value={confirmNewPassword}
                        onChange={(e) => setConfirmNewPassword(e.target.value)}
                        minLength={8}
                        required
                    />

                    {passwordError ? <div className="profile-error">{passwordError}</div> : null}
                    {passwordSuccess ? <div className="profile-success">{passwordSuccess}</div> : null}

                    <button className="btn btn-primary" type="submit" disabled={isChangingPassword}>
                        {isChangingPassword ? <Loader /> : "Change password"}
                    </button>
                </form>
            </section>

            <section className="profile-card">
                <h2>Account actions</h2>
                <div className="profile-section-form">
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
            </section>

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
