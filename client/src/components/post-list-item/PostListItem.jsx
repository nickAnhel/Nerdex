import { useContext, useEffect, useState, forwardRef } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";

import "./PostListItem.css";

import { StoreContext } from "../..";
import PostService from "../../service/PostService";

import Modal from "../modal/Modal";
import Loader from "../loader/Loader";
import PostModal from "../post-modal/PostModal"
import TagChip from "../tag-chip/TagChip";
import CommentIcon from "../icons/CommentIcon";
import DislikeIcon from "../icons/DislikeIcon";
import LikeIcon from "../icons/LikeIcon";


const PostListItem = forwardRef((props, ref) => {
    const { store } = useContext(StoreContext);
    const navigate = useNavigate();
    const location = useLocation();

    const [userProfilePhotoSrc, setUserProfilePhotoSrc] = useState(
        `${process.env.REACT_APP_STORAGE_URL}PPs@${props.post.user.user_id}?${performance.now()}`
    );

    const [post, setPost] = useState(props.post)
    const [myReaction, setMyReaction] = useState(props.post.my_reaction);

    const [isEditPostModalActive, setIsEditPostModalActive] = useState(false);
    const [isDeletePostModalActive, setIsDeletePostModalActive] = useState(false);
    const [isDeletingPost, setIsDeletingPost] = useState(false);

    useEffect(() => {
        setPost(props.post);
        setMyReaction(props.post.my_reaction);
        setUserProfilePhotoSrc(
            `${process.env.REACT_APP_STORAGE_URL}PPs@${props.post.user.user_id}?${performance.now()}`
        );
    }, [props.post]);

    const formatCreatedAt = (createdAt) => {
        const date = new Date(createdAt);
        return date.toLocaleDateString();
    };

    const handleLike = async () => {
        const res = myReaction === "like"
            ? await PostService.unlikePost(post.post_id)
            : await PostService.likePost(post.post_id);

        setMyReaction(res.data.my_reaction);
        setPost((prev) => ({
            ...prev,
            likes_count: res.data.likes_count,
            dislikes_count: res.data.dislikes_count,
            my_reaction: res.data.my_reaction,
        }));
    }

    const handleDislike = async () => {
        const res = myReaction === "dislike"
            ? await PostService.undislikePost(post.post_id)
            : await PostService.dislikePost(post.post_id);

        setMyReaction(res.data.my_reaction);
        setPost((prev) => ({
            ...prev,
            likes_count: res.data.likes_count,
            dislikes_count: res.data.dislikes_count,
            my_reaction: res.data.my_reaction,
        }));
    }

    const handleDeletePost = async () => {
        setIsDeletingPost(true);

        try {
            await PostService.deletePost(post.post_id);
            if (props.removePost) {
                props.removePost(post.post_id);
            }
            if (props.onDelete) {
                props.onDelete(post.post_id);
            }
            setIsDeletePostModalActive(false);

        } catch (e) {
            console.log(e);
            console.log(e?.response?.data?.detail);
        } finally {
            setIsDeletingPost(false);
            store.refreshPosts();
        }
    }

    const canReact = store.isAuthenticated && post.status === "published";
    const isLiked = myReaction === "like";
    const isDisliked = myReaction === "dislike";

    const buildPostQueryLocation = (postId) => {
        const nextSearchParams = new URLSearchParams(location.search);
        nextSearchParams.set("p", postId);

        return {
            pathname: location.pathname,
            search: `?${nextSearchParams.toString()}`,
        };
    };

    return (
        <div className="post-list-item" ref={ref}>
            <div className="header">
                <div className="post-meta">
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
                    <div className="post-badges">
                        {
                            post.status === "draft" &&
                            <span className="post-badge draft">Draft</span>
                        }
                        {
                            post.visibility === "private" &&
                            <span className="post-badge private">Private</span>
                        }
                    </div>
                </div>
                <span>
                    {formatCreatedAt(post.published_at || post.created_at)}
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
            {
                post.tags?.length > 0 &&
                <div className="post-tags">
                    {
                        post.tags.map((tag) => (
                            <TagChip
                                key={tag.tag_id || tag.slug}
                                slug={tag.slug}
                            />
                        ))
                    }
                </div>
            }
            <div className="actions">
                {
                    post.is_owner &&
                    <>
                        <img
                            onClick={() => { setIsDeletePostModalActive(true); }}
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
                    type="button"
                    className={`comment-count-button ${props.showDetailLink === false ? "static" : ""}`}
                    onClick={() => {
                        if (props.showDetailLink !== false) {
                            navigate(buildPostQueryLocation(post.post_id));
                        }
                    }}
                >
                    <span className="comment-count-icon" aria-hidden="true">
                        <CommentIcon />
                    </span>
                    <span>{post.comments_count}</span>
                </button>
                <button
                    className={isLiked ? "active" : ""}
                    onClick={handleLike}
                    disabled={!canReact}
                    aria-label={isLiked ? "Remove like" : "Like post"}
                >
                    <LikeIcon />
                    <span>{post.likes_count}</span>
                </button>
                <button
                    className={isDisliked ? "active" : ""}
                    onClick={handleDislike}
                    disabled={!canReact}
                    aria-label={isDisliked ? "Remove dislike" : "Dislike post"}
                >
                    <DislikeIcon />
                    <span>{post.dislikes_count}</span>
                </button>
            </div>

            <PostModal
                active={isEditPostModalActive}
                setActive={setIsEditPostModalActive}
                content={post.content}
                status={post.status}
                visibility={post.visibility}
                tags={post.tags}
                onSaved={setPost}
                savePostFunc={PostService.updatePost}
                navigateTo={(savedPost) => buildPostQueryLocation(savedPost.post_id)}
                postId={post.post_id}
                modalHeader={"Edit post"}
                buttonText={"Save"}
            />

            <Modal
                active={isDeletePostModalActive}
                setActive={() => {
                    if (!isDeletingPost) {
                        setIsDeletePostModalActive(false);
                    }
                }}
            >
                <div className="delete-post-modal">
                    <h2>Delete post?</h2>
                    <p>This action will hide the post from regular lists. You can&apos;t undo it from the interface.</p>
                    <div className="delete-post-modal-actions">
                        <button
                            type="button"
                            className="secondary"
                            onClick={() => setIsDeletePostModalActive(false)}
                            disabled={isDeletingPost}
                        >
                            Cancel
                        </button>
                        <button
                            type="button"
                            className="danger"
                            onClick={handleDeletePost}
                            disabled={isDeletingPost}
                        >
                            {isDeletingPost ? <Loader /> : "Delete"}
                        </button>
                    </div>
                </div>
            </Modal>
        </div>
    );
});

export default PostListItem;
