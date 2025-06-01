import { useState, useEffect, useContext } from "react";
import { observer } from "mobx-react-lite";
import { useNavigate } from "react-router-dom";
import "./ProfileForm.css"

import UserService from "../../service/UserService";

import { StoreContext } from "../..";

import Loader from "../loader/Loader";
import Modal from "../modal/Modal"


function ProfileForm() {
    const { store } = useContext(StoreContext);

    const navigate = useNavigate();

    const [isLoadingSave, setIsLoadingSave] = useState(false);
    const [isLoadingDelete, setIsLoadingDelete] = useState(false);
    const [isLoadingProfilePhotoUpdate, setIsLoadingProfilePhotoUpdate] = useState(false);
    const [isLoadingProfilePhotoDelete, setIsLoadingProfilePhotoDelete] = useState(false);
    const [imgSrc, setImgSrc] = useState(`${process.env.REACT_APP_STORAGE_URL}PPl@${store.user.user_id}?${performance.now()}`);

    // const [imgSrc, setImgSrc] = useState("/assets/profile.svg");

    const [isPhotoModalActive, setIsPhotoModalActive] = useState(false);

    const [username, setUsername] = useState("");

    const [profilePhoto, setProfilePhoto] = useState(null);
    const [selectedFile, setSelectedFile] = useState();
    const [preview, setPreview] = useState();

    useEffect(() => {
        setUsername(store.user.username);
    }, []);

        useEffect(() => {
        if (!selectedFile) {
            setPreview(undefined)
            return
        }

        const objectUrl = URL.createObjectURL(selectedFile)
        setPreview(objectUrl)

        return () => URL.revokeObjectURL(objectUrl)
    }, [selectedFile]);

    const handleReset = (e) => {
        e.preventDefault();
        setUsername(store.user.username);
    }

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
            handleReset();
        } catch (e) {
            console.log(e);
            console.log(e?.response?.data?.detail);
        }
        setIsLoadingSave(false);
    };

    const handleLogout = () => {
        store.logout();
        navigate("/login");
    }

    const handleDelete = async () => {
        setIsLoadingDelete(true);

        try {
            await UserService.deleteMe();
            store.logout();
            navigate("/login");
        } catch (e) {
            console.log(e);
            console.log(e?.response?.data?.detail);
        }

        setIsLoadingDelete(false);
    }

    const handleProfilePhotoUpdate = async () => {
        if (profilePhoto.size > 10000000) {
            // alertsContext.addAlert({
            //     text: "Profile photo size is too large",
            //     time: 2000,
            //     type: "error"
            // })
            return
        }

        setIsLoadingProfilePhotoUpdate(true);

        try {
            const formData = new FormData();
            formData.append("photo", profilePhoto);
            await UserService.updateProfilePhoto(formData);
            setImgSrc(`${process.env.REACT_APP_STORAGE_URL}PPl@${store.user.user_id}?${performance.now()}`);

            // alertsContext.addAlert({
            //     text: "Profile photo updated successfully",
            //     time: 2000,
            //     type: "success"
            // })

            store.changedProfilePhoto();
        } catch (e) {
            console.log(e);
            console.log(e?.response?.data?.detail);
        }

        setIsLoadingProfilePhotoUpdate(false);
        setIsPhotoModalActive(false);
    }

    const handleProfilePhotoDelete = async () => {
        setIsLoadingProfilePhotoDelete(true);

        try {
            await UserService.deleteProfilePhoto();

            // alertsContext.addAlert({
            //     text: "Profile deleted successfully",
            //     time: 2000,
            //     type: "success"
            // })
            store.changedProfilePhoto();
        } catch (e) {
            console.log(e);
            console.log(e?.response?.data?.detail);
        }

        setImgSrc("assets/profile.svg");
        setSelectedFile(undefined);
        setIsLoadingProfilePhotoDelete(false);
        setIsPhotoModalActive(false);
    }

    const handleSelectFile = e => {
        if (!e.target.files || e.target.files.length === 0) {
            setSelectedFile(undefined)
            return
        }

        setSelectedFile(e.target.files[0]);
    }

    return (
        <div className="profile-form">
            <form
                onSubmit={(e) => handleSubmit(e)}
            >
                <div className="form-section">
                    <img
                        src={imgSrc}
                        onError={() => { setImgSrc("assets/profile.svg") }}
                        alt="Profile Picture"
                    onClick={() => { setSelectedFile(undefined); setIsPhotoModalActive(true) }}
                    />

                    <input
                        type="text"
                        placeholder="Username"
                        value={username}
                        onChange={(e) => setUsername(e.target.value)}
                        maxLength={32}
                        pattern="[A-Za-z0-9._-]{1,32}"
                        required
                    />

                    <button
                        type="submit"
                        disabled={isLoadingSave}
                    >
                        {isLoadingSave ? <Loader /> : "Save"}
                    </button>

                    <button
                        type="reset"
                        className="reset"
                        onClick={(e) => handleReset(e)}
                    >
                        Reset
                    </button>
                </div>

                <div className="form-section">
                    <h2>Actions</h2>
                    <button
                        type="button"
                        className="logout"
                        onClick={handleLogout}
                    >
                        Log Out
                    </button>
                    <button
                        type="button"
                        className="delete"
                        onClick={handleDelete}
                        disabled={isLoadingDelete}
                    >
                        {isLoadingDelete ? <Loader /> : "Delete Account"}
                    </button>
                </div>
            </form>

            <Modal active={isPhotoModalActive} setActive={setIsPhotoModalActive}>
                <form className="image-form">
                    <label htmlFor="profile-photo-file">
                        <img
                            src={preview || imgSrc}
                            alt="Profile photo"
                        />

                        <input
                            type="file"
                            id="profile-photo-file"
                            accept=".png, .jpg, .jpeg"
                            onChange={e => { setProfilePhoto(e.target.files[0]); handleSelectFile(e) }}
                        />
                    </label>
                    <button
                        type="submit"
                        onClick={e => { e.preventDefault(); handleProfilePhotoUpdate() }}
                        disabled={profilePhoto == null}
                    >
                        {isLoadingProfilePhotoUpdate ? <Loader /> : "Save image"}
                    </button>

                    <button
                        className="delete"
                        onClick={e => { e.preventDefault(); handleProfilePhotoDelete() }}
                    >
                        {isLoadingProfilePhotoDelete ? <Loader /> : "Delete image"}
                    </button>
                </form>
            </Modal>
        </div>
    )
}


export default observer(ProfileForm)