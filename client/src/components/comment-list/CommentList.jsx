import "./CommentList.css";

import CommentListItem from "../comment-list-item/CommentListItem";


function CommentList({
    comments,
    onCommentsCountChange,
    onCommentChange,
    onCommentRemove,
    onReplyCreated,
}) {
    return (
        <div className="comment-list">
            {
                comments.map((comment) => (
                    <CommentListItem
                        key={comment.comment_id}
                        comment={comment}
                        onCommentsCountChange={onCommentsCountChange}
                        onCommentChange={onCommentChange}
                        onCommentRemove={onCommentRemove}
                        onReplyCreated={onReplyCreated}
                    />
                ))
            }
        </div>
    );
}

export default CommentList;
