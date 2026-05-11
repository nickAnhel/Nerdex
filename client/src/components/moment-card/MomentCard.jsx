import { forwardRef, useContext, useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import "./MomentCard.css";

import { StoreContext } from "../..";
import ContentService from "../../service/ContentService";
import MomentService from "../../service/MomentService";
import { getAvatarUrl } from "../../utils/avatar";
import { formatDuration } from "../video-card/VideoCard";
import CommentIcon from "../icons/CommentIcon";
import DeleteIcon from "../icons/DeleteIcon";
import DislikeIcon from "../icons/DislikeIcon";
import EditIcon from "../icons/EditIcon";
import LikeIcon from "../icons/LikeIcon";
import MomentsIcon from "../icons/MomentsIcon";
import OptionsIcon from "../icons/OptionsIcon";
import TagChip from "../tag-chip/TagChip";


const MomentCard = forwardRef(({ moment, removeItem }, ref) => {
    const { store } = useContext(StoreContext);
    const navigate = useNavigate();
    const menuRef = useRef(null);
    const [card, setCard] = useState(moment);
    const [avatarSrc, setAvatarSrc] = useState(getAvatarUrl(moment.user, "small"));
    const [isMenuOpen, setIsMenuOpen] = useState(false);

    useEffect(() => {
        setCard(moment);
        setAvatarSrc(getAvatarUrl(moment.user, "small"));
    }, [moment]);

    useEffect(() => {
        if (!isMenuOpen) {
            return undefined;
        }
        const handlePointerDown = (event) => {
            if (menuRef.current && !menuRef.current.contains(event.target)) {
                setIsMenuOpen(false);
            }
        };
        window.addEventListener("pointerdown", handlePointerDown);
        return () => window.removeEventListener("pointerdown", handlePointerDown);
    }, [isMenuOpen]);

    const momentId = card.moment_id || card.content_id;
    const canReact = store.isAuthenticated && card.status === "published" && card.processing_status === "ready";
    const isLiked = card.my_reaction === "like";
    const isDisliked = card.my_reaction === "dislike";
    const previewUrl = card.cover?.poster_url || card.cover?.preview_url || card.cover?.original_url;
    const durationLabel = formatDuration(card.duration_seconds);
    const canonicalPath = card.canonical_path || `/moments?moment=${momentId}`;

    const handleLike = async () => {
        const res = isLiked
            ? await ContentService.removeReaction(momentId, "like")
            : await ContentService.setReaction(momentId, "like");
        setCard((prevCard) => ({
            ...prevCard,
            likes_count: res.data.likes_count,
            dislikes_count: res.data.dislikes_count,
            my_reaction: res.data.my_reaction,
        }));
    };

    const handleDislike = async () => {
        const res = isDisliked
            ? await ContentService.removeReaction(momentId, "dislike")
            : await ContentService.setReaction(momentId, "dislike");
        setCard((prevCard) => ({
            ...prevCard,
            likes_count: res.data.likes_count,
            dislikes_count: res.data.dislikes_count,
            my_reaction: res.data.my_reaction,
        }));
    };

    const handleDelete = async () => {
        if (!window.confirm("Delete this Moment?")) {
            return;
        }
        await MomentService.deleteMoment(momentId);
        removeItem?.(momentId);
        store.refreshPosts?.();
    };

    return (
        <article className="moment-card" ref={ref}>
            <div className="moment-card-author-row">
                <Link to={`/people/@${card.user.username}`} className="moment-card-author">
                    <img
                        src={avatarSrc}
                        alt={`${card.user.username} profile`}
                        onError={() => setAvatarSrc("/assets/profile.svg")}
                    />
                    <span>{card.user.username}</span>
                </Link>
                <div className="moment-card-header-actions">
                    <span>{new Date(card.published_at || card.created_at).toLocaleDateString()}</span>
                    {
                        card.is_owner &&
                        <div className="moment-card-options" ref={menuRef}>
                            <button
                                type="button"
                                className="moment-card-options-trigger"
                                onClick={() => setIsMenuOpen((value) => !value)}
                                aria-label="Moment options"
                            >
                                <OptionsIcon />
                            </button>
                            {
                                isMenuOpen &&
                                <div className="moment-card-options-menu">
                                    <button type="button" onClick={() => navigate(`/moments/${momentId}/edit`)}>
                                        <EditIcon />
                                        <span>Edit</span>
                                    </button>
                                    <button type="button" className="danger" onClick={() => { void handleDelete(); }}>
                                        <DeleteIcon />
                                        <span>Delete</span>
                                    </button>
                                </div>
                            }
                        </div>
                    }
                </div>
            </div>

            <button
                type="button"
                className="moment-card-preview"
                onClick={() => navigate(canonicalPath)}
            >
                {
                    previewUrl
                        ? <img src={previewUrl} alt={card.caption || "Moment preview"} />
                        : <div className="moment-card-preview-empty"><MomentsIcon /></div>
                }
                <span className="moment-card-pill"><MomentsIcon /> Moment</span>
                {durationLabel && <span className="moment-card-duration">{durationLabel}</span>}
            </button>

            <div className="moment-card-body">
                <div className="moment-card-badges">
                    {card.status === "draft" && <span className="moment-card-badge draft">Draft</span>}
                    {card.visibility === "private" && <span className="moment-card-badge private">Private</span>}
                    {card.processing_status !== "ready" && <span className="moment-card-badge processing">{card.processing_status}</span>}
                </div>

                {card.caption && <p className="moment-card-caption">{card.caption}</p>}
                {
                    card.tags?.length > 0 &&
                    <div className="moment-card-tags">
                        {card.tags.map((tag) => <TagChip key={tag.tag_id || tag.slug} slug={tag.slug} />)}
                    </div>
                }
                {
                    card.processing_error && card.is_owner &&
                    <p className="moment-card-error">{card.processing_error}</p>
                }
            </div>

            <div className="moment-card-actions">
                <button type="button" onClick={() => navigate(canonicalPath)}>
                    <CommentIcon />
                    <span>{card.comments_count || 0}</span>
                </button>
                <button type="button" onClick={handleLike} className={isLiked ? "active" : ""} disabled={!canReact}>
                    <LikeIcon />
                    <span>{card.likes_count || 0}</span>
                </button>
                <button type="button" onClick={handleDislike} className={isDisliked ? "active" : ""} disabled={!canReact}>
                    <DislikeIcon />
                    <span>{card.dislikes_count || 0}</span>
                </button>
            </div>
        </article>
    );
});

export default MomentCard;
