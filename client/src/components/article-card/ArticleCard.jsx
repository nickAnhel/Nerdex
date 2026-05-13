import { forwardRef, useContext, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import "./ArticleCard.css";

import { StoreContext } from "../..";
import ArticleService from "../../service/ArticleService";

import TagChip from "../tag-chip/TagChip";
import CommentIcon from "../icons/CommentIcon";
import ContentShareButton from "../content-share-button/ContentShareButton";
import DislikeIcon from "../icons/DislikeIcon";
import LikeIcon from "../icons/LikeIcon";
import { getAvatarUrl } from "../../utils/avatar";
import { stripArticleFormatting } from "../../utils/articleMarkdown";


const ArticleCard = forwardRef(({ article }, ref) => {
    const { store } = useContext(StoreContext);
    const navigate = useNavigate();

    const [card, setCard] = useState(article);
    const [avatarSrc, setAvatarSrc] = useState(getAvatarUrl(article.user, "small"));

    useEffect(() => {
        setCard(article);
        setAvatarSrc(getAvatarUrl(article.user, "small"));
    }, [article]);

    const canReact = store.isAuthenticated && card.status === "published";
    const isLiked = card.my_reaction === "like";
    const isDisliked = card.my_reaction === "dislike";

    const handleLike = async () => {
        const res = isLiked
            ? await ArticleService.unlikeArticle(card.article_id)
            : await ArticleService.likeArticle(card.article_id);
        setCard((prevCard) => ({
            ...prevCard,
            likes_count: res.data.likes_count,
            dislikes_count: res.data.dislikes_count,
            my_reaction: res.data.my_reaction,
        }));
    };

    const handleDislike = async () => {
        const res = isDisliked
            ? await ArticleService.undislikeArticle(card.article_id)
            : await ArticleService.dislikeArticle(card.article_id);
        setCard((prevCard) => ({
            ...prevCard,
            likes_count: res.data.likes_count,
            dislikes_count: res.data.dislikes_count,
            my_reaction: res.data.my_reaction,
        }));
    };

    const publishedDate = new Date(card.published_at || card.created_at).toLocaleDateString();

    return (
        <article className="article-card" ref={ref}>
            <div className="article-card-topline">
                <Link to={`/people/@${card.user.username}`} className="article-card-author">
                    <img
                        src={avatarSrc}
                        alt={`${card.user.username} profile`}
                        onError={() => setAvatarSrc("/assets/profile.svg")}
                    />
                    <span>{card.user.username}</span>
                </Link>
                <div className="article-card-meta-inline">
                    <span>{publishedDate}</span>
                    <span>{card.reading_time_minutes} min read</span>
                </div>
            </div>

            {
                card.cover?.preview_url &&
                <button
                    type="button"
                    className="article-card-cover"
                    onClick={() => navigate(card.canonical_path)}
                >
                    <img src={card.cover.preview_url} alt={card.title} />
                </button>
            }

            <div className="article-card-body">
                <div className="article-card-statuses">
                    {
                        card.status === "draft" &&
                        <span className="article-card-badge draft">Draft</span>
                    }
                    {
                        card.visibility === "private" &&
                        <span className="article-card-badge private">Private</span>
                    }
                </div>

                <Link to={card.canonical_path} className="article-card-title">
                    {card.title}
                </Link>
                {
                    card.excerpt &&
                    <p className="article-card-excerpt">{stripArticleFormatting(card.excerpt)}</p>
                }

                {
                    card.tags?.length > 0 &&
                    <div className="article-card-tags">
                        {card.tags.map((tag) => <TagChip key={tag.tag_id || tag.slug} slug={tag.slug} />)}
                    </div>
                }
            </div>

            <div className="article-card-actions">
                <button type="button" onClick={() => navigate(card.canonical_path)}>
                    <CommentIcon />
                    <span>{card.comments_count}</span>
                </button>
                <button type="button" onClick={handleLike} className={isLiked ? "active" : ""} disabled={!canReact}>
                    <LikeIcon />
                    <span>{card.likes_count}</span>
                </button>
                <button type="button" onClick={handleDislike} className={isDisliked ? "active" : ""} disabled={!canReact}>
                    <DislikeIcon />
                    <span>{card.dislikes_count}</span>
                </button>
                <ContentShareButton
                    contentId={card.content_id || card.article_id}
                    contentTitle={card.title || "article"}
                />
            </div>
        </article>
    );
});

export default ArticleCard;
