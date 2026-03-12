import Loader from "../loader/Loader";
import CommentList from "../comment-list/CommentList";


function CommentReplies({
    comment,
    isOpen,
    isLoading,
    replies,
    hasMoreReplies,
    onToggle,
    onLoadMore,
    onCommentsCountChange,
    onCommentChange,
    onCommentRemove,
}) {
    if (comment.replies_count === 0) {
        return null;
    }

    return (
        <div className="comment-replies">
            <button
                type="button"
                className="comment-replies-toggle"
                onClick={onToggle}
            >
                {isOpen ? "Hide replies" : `Replies (${comment.replies_count})`}
            </button>

            {
                isOpen &&
                <div className="comment-replies-panel">
                    {
                        isLoading &&
                        <div className="comment-replies-loader">
                            <Loader />
                        </div>
                    }
                    {
                        !isLoading &&
                        <>
                            <CommentList
                                comments={replies}
                                onCommentsCountChange={onCommentsCountChange}
                                onCommentChange={onCommentChange}
                                onCommentRemove={onCommentRemove}
                            />
                            {
                                hasMoreReplies &&
                                <button
                                    type="button"
                                    className="comment-load-more"
                                    onClick={() => { void onLoadMore(); }}
                                >
                                    Load more replies
                                </button>
                            }
                        </>
                    }
                </div>
            }
        </div>
    );
}

export default CommentReplies;
