import { useState, forwardRef, useContext } from "react";
import { Link } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";

import "./PostListItem.css";

import { StoreContext } from "../..";
import PostService from "../../service/PostService";

import PostModal from "../post-modal/PostModal"


const PostListItem = forwardRef((props, ref) => {
    const { store } = useContext(StoreContext);

    const [userProfilePhotoSrc, setUserProfilePhotoSrc] = useState(
        `${process.env.REACT_APP_STORAGE_URL}PPs@${props.post.user.user_id}?${performance.now()}`
    );

    const [post, setPost] = useState(props.post)

    const [isLiked, setIsLiked] = useState(props.post.is_liked);
    const [isDisliked, setIsDisliked] = useState(props.post.is_disliked);

    const [isEditPostModalActive, setIsEditPostModalActive] = useState(false);

    const formatCreatedAt = (createdAt) => {
        const date = new Date(createdAt);
        return date.toLocaleDateString();
    };

    const handleLike = async () => {
        if (isLiked) {
            setIsLiked(false);

            const res = await PostService.unlikePost(props.post.post_id);

            setPost((prev) => ({
                ...prev,
                likes: res.data.likes,
                dislikes: res.data.dislikes,
            }));
        } else {
            setIsLiked(true);
            setIsDisliked(false);

            const res = await PostService.likePost(props.post.post_id);

            setPost((prev) => ({
                ...prev,
                likes: res.data.likes,
                dislikes: res.data.dislikes,
            }));
        }
    }

    const handleDislike = async () => {
        if (isDisliked) {
            setIsDisliked(false);

            const res = await PostService.undislikePost(props.post.post_id);

            setPost((prev) => ({
                ...prev,
                likes: res.data.likes,
                dislikes: res.data.dislikes,
            }));

        } else {
            setIsDisliked(true);
            setIsLiked(false);

            const res = await PostService.dislikePost(props.post.post_id);

            setPost((prev) => ({
                ...prev,
                likes: res.data.likes,
                dislikes: res.data.dislikes,
            }));
        }
    }

    const handleDeletePost = async (e) => {
        try {
            await PostService.deletePost(props.post.post_id);
            props.removePost(post.post_id);

        } catch (e) {
            console.log(e);
            console.log(e?.response?.data?.detail);
        } finally {
            store.refreshPosts();
        }
    }

    const setPostContent = (content) => {
        setPost(
            (prev) => ({
                ...prev,
                content: content,
            })
        );
    }

    return (
        <div className="post-list-item" ref={ref}>
            <div className="header">
                <Link to={`/people/@${post.user.username}`} className="author">
                    <img
                        src={userProfilePhotoSrc}
                        onError={() => { setUserProfilePhotoSrc("../../../assets/profile.svg") }}
                        alt={`${post.user.username} profile photo`}
                    />
                    <p>
                        {post.user.username}
                    </p>
                </Link>
                <span>
                    {formatCreatedAt(post.created_at)}
                </span>
            </div>
            <div className="content">
                <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    components={{
                        code({ node, inline, className, children, ...props }) {
                            const match = /language-(\w+)/.exec(className || "");
                            return !inline && match ? (
                                <SyntaxHighlighter
                                    style={oneDark}
                                    language={match[1]}
                                    PreTag="div"
                                    customStyle={{ margin: 0 }}
                                    {...props}
                                >
                                    {String(children).replace(/\n$/, "")}
                                </SyntaxHighlighter>
                            ) : (
                                <code className={className} {...props}>
                                    {children}
                                </code>
                            );
                        },
                    }}
                >
                    {post.content}
                </ReactMarkdown>
            </div>
            <div className="actions">
                {
                    store.user.user_id == props.post.user_id &&
                    <>
                        <img
                            onClick={(e) => { handleDeletePost(e); }}
                            src="../../../assets/delete.svg"
                            alt="Delete post"
                        />
                        <img
                            onClick={() => { setIsEditPostModalActive(true); }}
                            src="../../../assets/edit.svg"
                            alt="Edit post"
                        />
                    </>
                }

                <button
                    className={isLiked ? "active" : ""}
                    onClick={handleLike}
                    disabled={!store.isAuthenticated}
                >
                    🖒 {post.likes}
                </button>
                <button
                    className={isDisliked ? "active" : ""}
                    onClick={handleDislike}
                    disabled={!store.isAuthenticated}
                >
                    🖓 {post.dislikes}
                </button>
            </div>

            <PostModal
                active={isEditPostModalActive}
                setActive={setIsEditPostModalActive}
                content={post.content}
                setContent={setPostContent}
                savePostFunc={PostService.updatePost}
                postId={post.post_id}
                modalHeader={"Edit post"}
                buttonText={"Save"}
            />
        </div>
    );
});

export default PostListItem;
