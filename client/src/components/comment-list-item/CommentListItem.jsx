import { useContext, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import "./CommentListItem.css";

import { StoreContext } from "../..";
import CommentService from "../../service/CommentService";
import CommentActionMenu from "../comment-action-menu/CommentActionMenu";
import CommentComposer from "../comment-composer/CommentComposer";
import DislikeIcon from "../icons/DislikeIcon";
import LikeIcon from "../icons/LikeIcon";
import ReplyIcon from "../icons/ReplyIcon";
import CommentReplies from "../comment-replies/CommentReplies";
import Modal from "../modal/Modal";
import { getAvatarUrl } from "../../utils/avatar";


const REPLIES_PAGE_SIZE = 10;

function buildCommentAuthorPhotoSrc(author) {
    return getAvatarUrl(author, "small");
}


function CommentListItem({
    comment: initialComment,
    onCommentsCountChange,
    onCommentChange,
    onCommentRemove,
    onReplyCreated,
}) {
    const { store } = useContext(StoreContext);

    const [comment, setComment] = useState(initialComment);
    const [authorPhotoSrc, setAuthorPhotoSrc] = useState(
        initialComment.author ? buildCommentAuthorPhotoSrc(initialComment.author) : ""
    );
    const [isEditing, setIsEditing] = useState(false);
    const [isReplying, setIsReplying] = useState(false);
    const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
    const [isBusy, setIsBusy] = useState(false);
    const [replies, setReplies] = useState([]);
    const [repliesOffset, setRepliesOffset] = useState(0);
    const [hasMoreReplies, setHasMoreReplies] = useState(false);
    const [isRepliesOpen, setIsRepliesOpen] = useState(false);
    const [isRepliesLoading, setIsRepliesLoading] = useState(false);
    const [repliesLoaded, setRepliesLoaded] = useState(false);
    const [error, setError] = useState("");

    useEffect(() => {
        setComment(initialComment);
    }, [initialComment]);

    useEffect(() => {
        if (!initialComment.author) {
            setAuthorPhotoSrc("");
            return;
        }

        setAuthorPhotoSrc(buildCommentAuthorPhotoSrc(initialComment.author));
    }, [initialComment]);

    const visualDepthClassName = (() => {
        if (comment.depth <= 0) {
            return "depth-0";
        }
        if (comment.depth === 1) {
            return "depth-1";
        }
        return "depth-2";
    })();

    const canReact = store.isAuthenticated && !comment.is_deleted;
    const canReply = store.isAuthenticated && !comment.is_deleted;
    const isEdited = new Date(comment.updated_at).getTime() > new Date(comment.created_at).getTime();
    const shouldShowReplyContext = (
        comment.depth === 2 &&
        comment.reply_to_comment_depth === 2 &&
        comment.reply_to_comment_ref
    );

    const updateCurrentComment = (nextCommentOrUpdater) => {
        setComment((prevComment) => {
            const nextComment = typeof nextCommentOrUpdater === "function"
                ? nextCommentOrUpdater(prevComment)
                : nextCommentOrUpdater;

            if (nextComment !== null) {
                onCommentChange?.(nextComment);
            }

            return nextComment;
        });
    };

    const loadReplies = async ({ reset = false } = {}) => {
        setIsRepliesLoading(true);
        setError("");

        try {
            const nextOffset = reset ? 0 : repliesOffset;
            const res = await CommentService.getReplies(comment.comment_id, {
                offset: nextOffset,
                limit: REPLIES_PAGE_SIZE,
            });
            const fetchedReplies = res.data.items;
            setReplies((prevReplies) => (
                reset
                    ? fetchedReplies
                    : [...prevReplies, ...fetchedReplies]
            ));
            setRepliesOffset(nextOffset + fetchedReplies.length);
            setHasMoreReplies(res.data.has_more);
            setRepliesLoaded(true);
        } catch (fetchError) {
            setError(fetchError?.response?.data?.detail || "Failed to load replies.");
        } finally {
            setIsRepliesLoading(false);
        }
    };

    const toggleReplies = async () => {
        if (!isRepliesOpen && !repliesLoaded) {
            await loadReplies({ reset: true });
        }
        setIsRepliesOpen((prev) => !prev);
    };

    const handleLike = async () => {
        try {
            const res = comment.my_reaction === "like"
                ? await CommentService.unlikeComment(comment.comment_id)
                : await CommentService.likeComment(comment.comment_id);

            updateCurrentComment((prevComment) => ({
                ...prevComment,
                likes_count: res.data.likes_count,
                dislikes_count: res.data.dislikes_count,
                my_reaction: res.data.my_reaction,
            }));
        } catch (reactionError) {
            setError(reactionError?.response?.data?.detail || "Failed to update reaction.");
        }
    };

    const handleDislike = async () => {
        try {
            const res = comment.my_reaction === "dislike"
                ? await CommentService.undislikeComment(comment.comment_id)
                : await CommentService.dislikeComment(comment.comment_id);

            updateCurrentComment((prevComment) => ({
                ...prevComment,
                likes_count: res.data.likes_count,
                dislikes_count: res.data.dislikes_count,
                my_reaction: res.data.my_reaction,
            }));
        } catch (reactionError) {
            setError(reactionError?.response?.data?.detail || "Failed to update reaction.");
        }
    };

    const handleEditSubmit = async (bodyText) => {
        setIsBusy(true);
        setError("");

        try {
            const res = await CommentService.updateComment(comment.comment_id, {
                body_text: bodyText,
            });
            updateCurrentComment(res.data);
            setIsEditing(false);
        } catch (saveError) {
            setError(saveError?.response?.data?.detail || "Failed to update comment.");
        } finally {
            setIsBusy(false);
        }
    };

    const insertDisplayReply = async (createdReply) => {
        updateCurrentComment((prevComment) => ({
            ...prevComment,
            replies_count: prevComment.replies_count + 1,
        }));
        setIsRepliesOpen(true);

        if (repliesLoaded) {
            setReplies((prevReplies) => [...prevReplies, createdReply]);
            setRepliesOffset((prevOffset) => prevOffset + 1);
            return;
        }

        await loadReplies({ reset: true });
        setRepliesLoaded(true);
    };

    const handleReplySubmit = async (bodyText) => {
        setIsBusy(true);
        setError("");

        try {
            const res = await CommentService.createReply(comment.comment_id, {
                body_text: bodyText,
            });
            const createdReply = res.data;

            onCommentsCountChange?.(1);
            setIsReplying(false);

            if (createdReply.parent_comment_id === comment.comment_id) {
                await insertDisplayReply(createdReply);
            } else {
                onReplyCreated?.(createdReply);
            }
        } catch (saveError) {
            setError(saveError?.response?.data?.detail || "Failed to create reply.");
        } finally {
            setIsBusy(false);
        }
    };

    const handleDelete = async () => {
        setIsBusy(true);
        setError("");

        try {
            await CommentService.deleteComment(comment.comment_id);
            onCommentsCountChange?.(-1);

            if (comment.replies_count > 0) {
                updateCurrentComment((prevComment) => ({
                    ...prevComment,
                    author: null,
                    body_text: null,
                    is_deleted: true,
                    deleted_at: new Date().toISOString(),
                    likes_count: 0,
                    dislikes_count: 0,
                    my_reaction: null,
                }));
            } else {
                onCommentRemove?.(comment.comment_id);
            }
            setIsDeleteModalOpen(false);
        } catch (deleteError) {
            setError(deleteError?.response?.data?.detail || "Failed to delete comment.");
        } finally {
            setIsBusy(false);
        }
    };

    const handleNestedCommentChange = (updatedComment) => {
        setReplies((prevReplies) => prevReplies.map((reply) => (
            reply.comment_id === updatedComment.comment_id
                ? updatedComment
                : reply
        )));
    };

    const handleNestedCommentRemove = (removedCommentId) => {
        setReplies((prevReplies) => prevReplies.filter((reply) => reply.comment_id !== removedCommentId));
        setRepliesOffset((prevOffset) => Math.max(0, prevOffset - 1));

        setComment((prevComment) => {
            const nextRepliesCount = Math.max(0, prevComment.replies_count - 1);
            const nextComment = {
                ...prevComment,
                replies_count: nextRepliesCount,
            };

            if (prevComment.is_deleted && nextRepliesCount === 0) {
                onCommentRemove?.(prevComment.comment_id);
                return prevComment;
            }

            onCommentChange?.(nextComment);
            return nextComment;
        });
    };

    const handleNestedReplyCreated = async (createdReply) => {
        if (createdReply.parent_comment_id === comment.comment_id) {
            await insertDisplayReply(createdReply);
            return;
        }

        onReplyCreated?.(createdReply);
    };

    const jumpToReplyTarget = () => {
        if (!comment.reply_to_comment_ref) {
            return;
        }

        const parentElement = document.getElementById(`comment-${comment.reply_to_comment_ref.comment_id}`);
        if (parentElement) {
            parentElement.classList.remove("reply-target-highlight");
            void parentElement.offsetWidth;
            parentElement.classList.add("reply-target-highlight");
            parentElement.scrollIntoView({
                behavior: "smooth",
                block: "center",
            });
            window.setTimeout(() => {
                parentElement.classList.remove("reply-target-highlight");
            }, 1000);
        }
    };

    return (
        <>
            <article
                id={`comment-${comment.comment_id}`}
                className={`comment-list-item ${visualDepthClassName} ${comment.is_deleted ? "deleted" : ""}`}
            >
                <div className="comment-card">
                    <header className="comment-card-header">
                        <div className="comment-card-meta">
                            {
                                comment.is_deleted
                                    ? <span className="comment-tombstone">deleted at {new Date(comment.deleted_at).toLocaleString()}</span>
                                    : (
                                        <>
                                            <Link to={`/people/@${comment.author.username}`} className="comment-author">
                                                <img
                                                    src={authorPhotoSrc}
                                                    onError={() => { setAuthorPhotoSrc("/assets/profile.svg"); }}
                                                    alt={`${comment.author.username} avatar`}
                                                />
                                                {comment.author.username}
                                            </Link>
                                            <span className="comment-date">
                                                {new Date(comment.created_at).toLocaleString()}
                                            </span>
                                            {
                                                isEdited &&
                                                <span className="comment-edited">
                                                    edited at {new Date(comment.updated_at).toLocaleString()}
                                                </span>
                                            }
                                        </>
                                    )
                            }
                        </div>
                        {
                            comment.is_owner && !comment.is_deleted &&
                            <CommentActionMenu
                                onEdit={() => setIsEditing(true)}
                                onDelete={() => setIsDeleteModalOpen(true)}
                            />
                        }
                    </header>

                    {
                        shouldShowReplyContext &&
                        <div className="comment-parent-line">
                            {
                                comment.reply_to_username
                                    ? (
                                        <button
                                            type="button"
                                            className="comment-parent-link"
                                            onClick={jumpToReplyTarget}
                                        >
                                            {`Reply to @${comment.reply_to_username}`}
                                        </button>
                                    )
                                    : (
                                        <span className="comment-parent-text">
                                            Reply to deleted comment
                                        </span>
                                    )
                            }
                        </div>
                    }

                    {
                        !comment.is_deleted && isEditing &&
                        <CommentComposer
                            initialValue={comment.body_text}
                            placeholder="Update your comment"
                            submitLabel="Save"
                            onSubmit={handleEditSubmit}
                            onCancel={() => {
                                setIsEditing(false);
                                setError("");
                            }}
                            isSubmitting={isBusy}
                            autoFocus={true}
                        />
                    }

                    {
                        !comment.is_deleted && !isEditing &&
                        <p className="comment-body">{comment.body_text}</p>
                    }

                    {
                        !comment.is_deleted &&
                        <div className="comment-actions">
                            <div className="comment-reaction-group">
                                <button
                                    type="button"
                                    className={`comment-action-button like ${comment.my_reaction === "like" ? "active" : ""}`}
                                    onClick={() => { void handleLike(); }}
                                    disabled={!canReact}
                                    aria-label={comment.my_reaction === "like" ? "Remove like" : "Like comment"}
                                >
                                    <LikeIcon />
                                    <span className="comment-action-count">{comment.likes_count}</span>
                                </button>
                                <button
                                    type="button"
                                    className={`comment-action-button dislike ${comment.my_reaction === "dislike" ? "active" : ""}`}
                                    onClick={() => { void handleDislike(); }}
                                    disabled={!canReact}
                                    aria-label={comment.my_reaction === "dislike" ? "Remove dislike" : "Dislike comment"}
                                >
                                    <DislikeIcon />
                                    <span className="comment-action-count">{comment.dislikes_count}</span>
                                </button>
                            </div>
                            {
                                canReply &&
                                <button
                                    type="button"
                                    className={`comment-action-button reply ${isReplying ? "active" : ""}`}
                                    onClick={() => setIsReplying((prev) => !prev)}
                                    aria-label={isReplying ? "Cancel reply" : "Reply to comment"}
                                >
                                    <ReplyIcon />
                                </button>
                            }
                        </div>
                    }

                    {
                        isReplying &&
                        <div className="comment-inline-composer">
                            <CommentComposer
                                placeholder={
                                    `Reply to ${comment.is_deleted ? "this thread" : `@${comment.author.username}`}`
                                }
                                submitLabel="Reply"
                                onSubmit={handleReplySubmit}
                                onCancel={() => {
                                    setIsReplying(false);
                                    setError("");
                                }}
                                isSubmitting={isBusy}
                                autoFocus={true}
                            />
                        </div>
                    }

                    {
                        error &&
                        <p className="comment-error">{error}</p>
                    }
                </div>

                <CommentReplies
                    comment={comment}
                    isOpen={isRepliesOpen}
                    isLoading={isRepliesLoading}
                    replies={replies}
                    hasMoreReplies={hasMoreReplies}
                    onToggle={() => { void toggleReplies(); }}
                    onLoadMore={() => loadReplies()}
                    onCommentsCountChange={onCommentsCountChange}
                    onCommentChange={handleNestedCommentChange}
                    onCommentRemove={handleNestedCommentRemove}
                    onReplyCreated={(createdReply) => { void handleNestedReplyCreated(createdReply); }}
                />
            </article>

            <Modal
                active={isDeleteModalOpen}
                setActive={() => {
                    if (!isBusy) {
                        setIsDeleteModalOpen(false);
                    }
                }}
            >
                <div className="delete-comment-modal">
                    <h2>Delete comment?</h2>
                    <p>
                        {
                            comment.replies_count > 0
                                ? "The comment body and author will be hidden, but the thread will stay visible for replies."
                                : "The comment will disappear from the thread for regular viewers."
                        }
                    </p>
                    <div className="delete-comment-modal-actions">
                        <button
                            type="button"
                            className="btn btn-secondary"
                            onClick={() => setIsDeleteModalOpen(false)}
                            disabled={isBusy}
                        >
                            Cancel
                        </button>
                        <button
                            type="button"
                            className="btn btn-danger"
                            onClick={() => { void handleDelete(); }}
                            disabled={isBusy}
                        >
                            {isBusy ? "Deleting..." : "Delete"}
                        </button>
                    </div>
                </div>
            </Modal>
        </>
    );
}

export default CommentListItem;
