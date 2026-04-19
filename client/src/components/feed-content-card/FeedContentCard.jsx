import PostListItem from "../post-list-item/PostListItem";
import ArticleCard from "../article-card/ArticleCard";


function FeedContentCard({ item, removeItem, forwardedRef = null }) {
    if (item.content_type === "article") {
        return (
            <ArticleCard
                ref={forwardedRef}
                article={{
                    ...item,
                    article_id: item.content_id,
                }}
                removeItem={removeItem}
            />
        );
    }

    const post = {
        ...item,
        post_id: item.content_id,
        content: item.post_content,
    };

    return (
        <PostListItem
            ref={forwardedRef}
            post={post}
            removePost={removeItem}
        />
    );
}

export default FeedContentCard;
