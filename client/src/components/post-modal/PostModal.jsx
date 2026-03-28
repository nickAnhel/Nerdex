import { useContext, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import "./PostModal.css"

import { StoreContext } from "../..";

import Modal from "../modal/Modal";
import Loader from "../loader/Loader";
import TagInput from "../tag-input/TagInput";
import { areTagListsEqual, dedupeTags, normalizeTagList } from "../../utils/tags";

const EMPTY_TAGS = [];


function PostModal({
    active,
    setActive,

    postId,
    content,
    status = "published",
    visibility = "public",
    tags = null,
    savePostFunc,
    navigateTo,
    onSaved,

    modalHeader,
    buttonText
}) {
    const { store } = useContext(StoreContext);

    const navigate = useNavigate();
    const incomingTags = tags ?? EMPTY_TAGS;
    const normalizedIncomingTags = useMemo(
        () => normalizeTagList(incomingTags),
        [incomingTags]
    );

    const [postContent, setPostContent] = useState(content || "");
    const [postStatus, setPostStatus] = useState(status);
    const [postVisibility, setPostVisibility] = useState(visibility);
    const [postTags, setPostTags] = useState(normalizedIncomingTags);
    const [initialPostTags, setInitialPostTags] = useState(normalizedIncomingTags);
    const [tagInputState, setTagInputState] = useState({
        value: "",
        normalizedValue: "",
        error: "",
    });
    const [isLoadingSavePost, setIsLoadingSavePost] = useState(false);
    const [saveError, setSaveError] = useState("");

    useEffect(() => {
        setPostContent(content || "");
        setPostStatus(status);
        setPostVisibility(visibility);
        setPostTags(normalizedIncomingTags);
        setInitialPostTags(normalizedIncomingTags);
        setTagInputState({
            value: "",
            normalizedValue: "",
            error: "",
        });
        setSaveError("");
    }, [active, content, status, visibility, normalizedIncomingTags]);

    const handleSavePost = async (event) => {
        event.preventDefault();
        setSaveError("");

        if (tagInputState.error) {
            setSaveError(tagInputState.error);
            return;
        }

        const nextTags = tagInputState.normalizedValue
            ? dedupeTags([...postTags, tagInputState.normalizedValue])
            : postTags;

        if (nextTags !== postTags) {
            setPostTags(nextTags);
        }

        setIsLoadingSavePost(true);

        try {
            const postData = {
                content: postContent,
                status: postStatus,
                visibility: postVisibility,
            }

            if (postId) {
                if (!areTagListsEqual(nextTags, initialPostTags)) {
                    postData.tags = nextTags;
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

        } catch (e) {
            console.log(e);
            console.log(e?.response?.data?.detail);
            setSaveError(e?.response?.data?.detail || "Failed to save post");

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
                        {
                            postStatus === "draft" &&
                            <p className="post-settings-hint">
                                Drafts are visible only to you until published.
                            </p>
                        }
                    </div>
                </div>

                {
                    saveError &&
                    <div className="post-save-error">{saveError}</div>
                }

                <button
                    className="btn btn-primary btn-block"
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
