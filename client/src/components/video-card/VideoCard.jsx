import { forwardRef, useContext, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import "./VideoCard.css";

import { StoreContext } from "../..";
import ContentService from "../../service/ContentService";
import CommentIcon from "../icons/CommentIcon";
import ContentShareButton from "../content-share-button/ContentShareButton";
import DislikeIcon from "../icons/DislikeIcon";
import LikeIcon from "../icons/LikeIcon";
import TagChip from "../tag-chip/TagChip";
import { getAvatarUrl } from "../../utils/avatar";


export function formatDuration(seconds) {
    if (!Number.isFinite(Number(seconds))) {
        return "";
    }
    const total = Math.max(0, Math.floor(Number(seconds)));
    const hrs = Math.floor(total / 3600);
    const mins = Math.floor((total % 3600) / 60);
    const secs = total % 60;
    if (hrs > 0) {
        return `${hrs}:${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
    }
    return `${mins}:${String(secs).padStart(2, "0")}`;
}

const VideoCard = forwardRef(({ video }, ref) => {
    const { store } = useContext(StoreContext);
    const navigate = useNavigate();
    const [card, setCard] = useState(video);
    const [avatarSrc, setAvatarSrc] = useState(getAvatarUrl(video.user, "small"));

    useEffect(() => {
        setCard(video);
        setAvatarSrc(getAvatarUrl(video.user, "small"));
    }, [video]);

    const canReact = store.isAuthenticated && card.status === "published" && card.processing_status === "ready";
    const isLiked = card.my_reaction === "like";
    const isDisliked = card.my_reaction === "dislike";
    const previewUrl = card.cover?.preview_url || card.cover?.original_url;
    const durationLabel = formatDuration(card.duration_seconds);

    const handleLike = async () => {
        const res = isLiked
            ? await ContentService.removeReaction(card.content_id || card.video_id, "like")
            : await ContentService.setReaction(card.content_id || card.video_id, "like");
        setCard((prevCard) => ({
            ...prevCard,
            likes_count: res.data.likes_count,
            dislikes_count: res.data.dislikes_count,
            my_reaction: res.data.my_reaction,
        }));
    };

    const handleDislike = async () => {
        const res = isDisliked
            ? await ContentService.removeReaction(card.content_id || card.video_id, "dislike")
            : await ContentService.setReaction(card.content_id || card.video_id, "dislike");
        setCard((prevCard) => ({
            ...prevCard,
            likes_count: res.data.likes_count,
            dislikes_count: res.data.dislikes_count,
            my_reaction: res.data.my_reaction,
        }));
    };

    return (
        <article className="video-card" ref={ref}>
            <div className="video-card-author-row">
                <Link to={`/people/@${card.user.username}`} className="video-card-author">
                    <img
                        src={avatarSrc}
                        alt={`${card.user.username} profile`}
                        onError={() => setAvatarSrc("/assets/profile.svg")}
                    />
                    <span>{card.user.username}</span>
                </Link>
                <span>{new Date(card.published_at || card.created_at).toLocaleDateString()}</span>
            </div>

            <button
                type="button"
                className={`video-card-preview ${card.orientation || ""}`}
                onClick={() => navigate(card.canonical_path)}
            >
                {
                    previewUrl
                        ? <img src={previewUrl} alt={card.title || "Video preview"} />
                        : <div className="video-card-preview-empty">Preview unavailable</div>
                }
                <span className="video-card-play">Play</span>
                {
                    durationLabel &&
                    <span className="video-card-duration">{durationLabel}</span>
                }
            </button>

            <div className="video-card-body">
                <div className="video-card-badges">
                    {
                        card.status === "draft" &&
                        <span className="video-card-badge draft">Draft</span>
                    }
                    {
                        card.visibility === "private" &&
                        <span className="video-card-badge private">Private</span>
                    }
                    {
                        card.processing_status !== "ready" &&
                        <span className="video-card-badge processing">{card.processing_status}</span>
                    }
                </div>

                <Link to={card.canonical_path} className="video-card-title">
                    {card.title || "Untitled video"}
                </Link>
                {
                    card.excerpt &&
                    <p className="video-card-description">{card.excerpt}</p>
                }
                {
                    card.tags?.length > 0 &&
                    <div className="video-card-tags">
                        {card.tags.map((tag) => <TagChip key={tag.tag_id || tag.slug} slug={tag.slug} />)}
                    </div>
                }
                {
                    card.processing_error && card.is_owner &&
                    <p className="video-card-error">{card.processing_error}</p>
                }
            </div>

            <div className="video-card-actions">
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
                    contentId={card.content_id || card.video_id}
                    contentTitle={card.title || "video"}
                />
            </div>
        </article>
    );
});

export default VideoCard;
