import { useContext, useEffect, useState } from "react";

import "./CommentSection.css";

import { StoreContext } from "../..";
import CommentService from "../../service/CommentService";
import CommentComposer from "../comment-composer/CommentComposer";
import CommentList from "../comment-list/CommentList";
import Loader from "../loader/Loader";


const ROOT_COMMENTS_PAGE_SIZE = 20;


function CommentSection({ contentId, isEnabled, onCommentsCountChange }) {
    const { store } = useContext(StoreContext);

    const [comments, setComments] = useState([]);
    const [offset, setOffset] = useState(0);
    const [hasMore, setHasMore] = useState(false);
    const [isLoading, setIsLoading] = useState(false);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [error, setError] = useState("");

    useEffect(() => {
        setComments([]);
        setOffset(0);
        setHasMore(false);
        setError("");

        if (!contentId || !isEnabled) {
            return;
        }

        const loadInitialComments = async () => {
            setIsLoading(true);
            setError("");

            try {
                const res = await CommentService.getContentComments(contentId, {
                    offset: 0,
                    limit: ROOT_COMMENTS_PAGE_SIZE,
                });
                setComments(res.data.items);
                setOffset(res.data.items.length);
                setHasMore(res.data.has_more);
            } catch (fetchError) {
                setError(fetchError?.response?.data?.detail || "Failed to load comments.");
            } finally {
                setIsLoading(false);
            }
        };

        void loadInitialComments();
    }, [contentId, isEnabled]);

    const fetchComments = async () => {
        if (!contentId || !isEnabled) {
            return;
        }

        setIsLoading(true);
        setError("");

        try {
            const res = await CommentService.getContentComments(contentId, {
                offset,
                limit: ROOT_COMMENTS_PAGE_SIZE,
            });
            const fetchedComments = res.data.items;
            setComments((prevComments) => [...prevComments, ...fetchedComments]);
            setOffset((prevOffset) => prevOffset + fetchedComments.length);
            setHasMore(res.data.has_more);
        } catch (fetchError) {
            setError(fetchError?.response?.data?.detail || "Failed to load comments.");
        } finally {
            setIsLoading(false);
        }
    };

    const handleCreateRootComment = async (bodyText) => {
        setIsSubmitting(true);
        setError("");

        try {
            const res = await CommentService.createContentComment(contentId, {
                body_text: bodyText,
            });
            setComments((prevComments) => [res.data, ...prevComments]);
            setOffset((prevOffset) => prevOffset + 1);
            onCommentsCountChange?.(1);
        } catch (submitError) {
            setError(submitError?.response?.data?.detail || "Failed to create comment.");
            throw submitError;
        } finally {
            setIsSubmitting(false);
        }
    };

    const handleRootCommentChange = (updatedComment) => {
        setComments((prevComments) => prevComments.map((comment) => (
            comment.comment_id === updatedComment.comment_id
                ? updatedComment
                : comment
        )));
    };

    const handleRootCommentRemove = (commentId) => {
        setComments((prevComments) => prevComments.filter((comment) => comment.comment_id !== commentId));
        setOffset((prevOffset) => Math.max(0, prevOffset - 1));
    };

    if (!isEnabled) {
        return (
            <section className="comment-section">
                <div className="comment-section-state">
                    Comments are available only for published content.
                </div>
            </section>
        );
    }

    return (
        <section className="comment-section">
            <div className="comment-section-header">
                <h3>Comments</h3>
            </div>

            {
                store.isAuthenticated
                    ? (
                        <CommentComposer
                            placeholder="Write a comment"
                            submitLabel="Comment"
                            onSubmit={handleCreateRootComment}
                            isSubmitting={isSubmitting}
                        />
                    )
                    : (
                        <div className="comment-section-state">
                            Log in to write comments and react to threads.
                        </div>
                    )
            }

            {
                error &&
                <p className="comment-section-error">{error}</p>
            }

            {
                isLoading && comments.length === 0 &&
                <div className="comment-section-loader">
                    <Loader />
                </div>
            }

            {
                !isLoading && comments.length === 0 &&
                <div className="comment-section-state">
                    No comments yet.
                </div>
            }

            {
                comments.length > 0 &&
                <CommentList
                    comments={comments}
                    onCommentsCountChange={onCommentsCountChange}
                    onCommentChange={handleRootCommentChange}
                    onCommentRemove={handleRootCommentRemove}
                />
            }

            {
                hasMore &&
                <button
                    type="button"
                    className="comment-section-load-more"
                    onClick={() => { void fetchComments(); }}
                    disabled={isLoading}
                >
                    {isLoading ? "Loading..." : "Load more comments"}
                </button>
            }
        </section>
    );
}

export default CommentSection;
