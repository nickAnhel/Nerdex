import PostListItem from "../post-list-item/PostListItem";
import ArticleCard from "../article-card/ArticleCard";
import VideoCard from "../video-card/VideoCard";


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

    if (item.content_type === "video") {
        return (
            <VideoCard
                ref={forwardedRef}
                video={{
                    ...item,
                    video_id: item.content_id,
                }}
                removeItem={removeItem}
            />
        );
    }

    if (item.content_type === "post") {
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

    return null;
}

export default FeedContentCard;
