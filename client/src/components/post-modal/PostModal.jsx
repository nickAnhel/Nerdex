import { useContext, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import "./PostModal.css"

import { StoreContext } from "../..";

import Modal from "../modal/Modal";
import Loader from "../loader/Loader";


function PostModal({
    active,
    setActive,

    postId,
    content,
    status = "published",
    visibility = "public",
    savePostFunc,
    navigateTo,
    onSaved,

    modalHeader,
    buttonText
}) {
    const { store } = useContext(StoreContext);

    const navigate = useNavigate();

    const [postContent, setPostContent] = useState(content || "");
    const [postStatus, setPostStatus] = useState(status);
    const [postVisibility, setPostVisibility] = useState(visibility);
    const [isLoadingSavePost, setIsLoadingSavePost] = useState(false);

    useEffect(() => {
        setPostContent(content || "");
        setPostStatus(status);
        setPostVisibility(visibility);
    }, [active, content, status, visibility]);

    const handleSavePost = async (event) => {
        event.preventDefault();
        setIsLoadingSavePost(true);

        try {
            const postData = {
                content: postContent,
                status: postStatus,
                visibility: postVisibility,
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

        } catch (e) {
            console.log(e);
            console.log(e?.response?.data?.detail);

        } finally {
            setIsLoadingSavePost(false);
        }
    }

    return (
        <Modal active={active} setActive={setActive}>
            <form id="create-post-form">
                <h1>{modalHeader}</h1>

                <div className="post-content-wrapper">
                    <textarea
                        className="post-content"
                        placeholder="Type something..."
                        value={postContent}
                        onChange={(e) => setPostContent(e.target.value)}
                        minLength={1}
                        maxLength={2048}
                        required
                    ></textarea>
                    <span className="post-content-length">{postContent.trim().length} / 2048</span>
                </div>

                <div className="post-settings">
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
                        {
                            postStatus === "draft" &&
                            <p className="post-settings-hint">
                                Drafts are visible only to you until published.
                            </p>
                        }
                    </div>
                </div>

                <button
                    disabled={postContent.trim().length < 1}
                    onClick={(e) => { handleSavePost(e); }}
                >
                    {isLoadingSavePost ? <Loader /> : buttonText}
                </button>
            </form>
        </Modal>
    )
}

export default PostModal;
