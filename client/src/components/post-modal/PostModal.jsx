import { useState, useContext } from "react";
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
    setContent,
    savePostFunc,
    navigateTo,

    modalHeader,
    buttonText
}) {
    const { store } = useContext(StoreContext);

    const navigate = useNavigate();

    const [postContent, setPostContent] = useState(content || "");
    const [isLoadingSavePost, setIsLoadingSavePost] = useState(false);

    const handleSavePost = async (event) => {
        setIsLoadingSavePost(true);
        event.preventDefault();

        try {
            const postData = {
                content: postContent,
            }
            await savePostFunc(postId, postData);

            if (setContent) {
                setContent(postContent);
            }

            if (navigateTo) {
                navigate(navigateTo);
            }

        } catch (e) {
            console.log(e);
            console.log(e?.response?.data?.detail);

        } finally {
            setIsLoadingSavePost(false);
            setActive(false);
            store.refreshPosts();
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
                        maxLength={8192}
                        required
                    ></textarea>
                    <span className="post-content-length">{postContent.trim().length} / 8192</span>
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