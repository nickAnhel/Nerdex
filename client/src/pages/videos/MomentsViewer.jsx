import { useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import "../../components/video-player/VideoPlayer.css";
import "./MomentsViewer.css";

import { StoreContext } from "../..";
import CommentSection from "../../components/comment-section/CommentSection";
import ChevronIcon from "../../components/icons/ChevronIcon";
import CloseIcon from "../../components/icons/CloseIcon";
import CommentIcon from "../../components/icons/CommentIcon";
import DeleteIcon from "../../components/icons/DeleteIcon";
import DislikeIcon from "../../components/icons/DislikeIcon";
import EditIcon from "../../components/icons/EditIcon";
import LikeIcon from "../../components/icons/LikeIcon";
import OptionsIcon from "../../components/icons/OptionsIcon";
import Loader from "../../components/loader/Loader";
import VideoPlayer from "../../components/video-player/VideoPlayer";
import ContentService from "../../service/ContentService";
import MomentService from "../../service/MomentService";


const PAGE_SIZE = 12;


function MomentsViewer() {
    const navigate = useNavigate();
    const [searchParams] = useSearchParams();
    const [moments, setMoments] = useState([]);
    const [activeIndex, setActiveIndex] = useState(0);
    const [offset, setOffset] = useState(0);
    const [hasMore, setHasMore] = useState(true);
    const [isLoading, setIsLoading] = useState(true);
    const [isLoadingMore, setIsLoadingMore] = useState(false);
    const [error, setError] = useState("");
    const [commentsMomentId, setCommentsMomentId] = useState(null);
    const touchStartYRef = useRef(null);

    const targetMomentId = searchParams.get("moment");

    const loadMoments = useCallback(async ({ append = false } = {}) => {
        if (append) {
            setIsLoadingMore(true);
        } else {
            setIsLoading(true);
        }
        setError("");

        try {
            const nextOffset = append ? offset : 0;
            const res = await MomentService.getFeed({ offset: nextOffset, limit: PAGE_SIZE });
            const feedItems = res.data || [];
            let fetched = feedItems;
            let nextActiveIndex = 0;

            if (!append && targetMomentId) {
                const foundIndex = fetched.findIndex((item) => (
                    String(item.moment_id || item.content_id) === targetMomentId
                ));
                if (foundIndex >= 0) {
                    nextActiveIndex = foundIndex;
                } else {
                    try {
                        const detailRes = await MomentService.getMoment(targetMomentId);
                        const targetMoment = detailRes.data;
                        fetched = [
                            targetMoment,
                            ...fetched.filter((item) => (
                                (item.moment_id || item.content_id) !== (targetMoment.moment_id || targetMoment.content_id)
                            )),
                        ];
                    } catch {
                        // If the deep-linked Moment is not visible, keep the public feed usable.
                    }
                }
            }

            setMoments((prev) => append ? [...prev, ...fetched] : fetched);
            setOffset(nextOffset + feedItems.length);
            setHasMore(feedItems.length === PAGE_SIZE);
            if (!append) {
                setActiveIndex(nextActiveIndex);
            }
        } catch (fetchError) {
            setError(fetchError?.response?.data?.detail || "Failed to load Moments.");
        } finally {
            setIsLoading(false);
            setIsLoadingMore(false);
        }
    }, [offset, targetMomentId]);

    useEffect(() => {
        void loadMoments();
    }, []); // eslint-disable-line react-hooks/exhaustive-deps

    const activeMoment = moments[activeIndex] || null;

    const goTo = useCallback((nextIndex) => {
        setActiveIndex((current) => {
            const bounded = Math.max(0, Math.min(nextIndex, Math.max(0, moments.length - 1)));
            if (bounded >= moments.length - 3 && hasMore && !isLoadingMore) {
                void loadMoments({ append: true });
            }
            return bounded;
        });
    }, [hasMore, isLoadingMore, loadMoments, moments.length]);

    const goNext = useCallback(() => goTo(activeIndex + 1), [activeIndex, goTo]);
    const goPrev = useCallback(() => goTo(activeIndex - 1), [activeIndex, goTo]);

    useEffect(() => {
        const handleKeyDown = (event) => {
            const target = event.target;
            const isEditableTarget = target instanceof HTMLElement && (
                target.tagName === "INPUT"
                || target.tagName === "TEXTAREA"
                || target.tagName === "SELECT"
                || target.isContentEditable
            );
            if (isEditableTarget) {
                return;
            }

            if (["ArrowDown", "PageDown", "j", "J"].includes(event.key)) {
                event.preventDefault();
                goNext();
            } else if (["ArrowUp", "PageUp", "k", "K"].includes(event.key)) {
                event.preventDefault();
                goPrev();
            } else if (event.key === "Escape" && commentsMomentId) {
                setCommentsMomentId(null);
            }
        };

        window.addEventListener("keydown", handleKeyDown);
        return () => window.removeEventListener("keydown", handleKeyDown);
    }, [commentsMomentId, goNext, goPrev]);

    const handleWheel = (event) => {
        if (Math.abs(event.deltaY) < 25) {
            return;
        }
        event.preventDefault();
        if (event.deltaY > 0) {
            goNext();
        } else {
            goPrev();
        }
    };

    const handleTouchStart = (event) => {
        touchStartYRef.current = event.touches?.[0]?.clientY ?? null;
    };

    const handleTouchEnd = (event) => {
        const startY = touchStartYRef.current;
        touchStartYRef.current = null;
        const endY = event.changedTouches?.[0]?.clientY ?? null;
        if (startY === null || endY === null) {
            return;
        }

        const deltaY = startY - endY;
        if (Math.abs(deltaY) < 48) {
            return;
        }
        if (deltaY > 0) {
            goNext();
        } else {
            goPrev();
        }
    };

    const updateMoment = useCallback((momentId, patch) => {
        setMoments((items) => items.map((item) => (
            item.moment_id === momentId || item.content_id === momentId
                ? { ...item, ...patch }
                : item
        )));
    }, []);

    const removeMoment = useCallback((momentId) => {
        setMoments((items) => {
            const nextItems = items.filter((item) => (
                (item.moment_id || item.content_id) !== momentId
            ));
            setActiveIndex((currentIndex) => Math.min(currentIndex, Math.max(0, nextItems.length - 1)));
            return nextItems;
        });
        if (commentsMomentId === momentId) {
            setCommentsMomentId(null);
        }
    }, [commentsMomentId]);

    if (isLoading) {
        return (
            <div className="moments-viewer-state">
                <Loader />
            </div>
        );
    }

    if (error) {
        return (
            <div className="moments-viewer-state">
                <p>{error}</p>
                <button type="button" onClick={() => { void loadMoments(); }}>Retry</button>
            </div>
        );
    }

    if (!activeMoment) {
        return (
            <div className="moments-viewer-state">
                <p>No Moments yet.</p>
            </div>
        );
    }

    return (
        <div
            className="moments-viewer"
            onWheel={handleWheel}
            onTouchStart={handleTouchStart}
            onTouchEnd={handleTouchEnd}
        >
            <button
                type="button"
                className="moments-nav-button prev"
                onClick={goPrev}
                disabled={activeIndex === 0}
                aria-label="Previous Moment"
            >
                <ChevronIcon direction="up" />
            </button>

            <div className="moments-stage">
                <div
                    className="moments-track"
                    style={{ transform: `translate3d(0, -${activeIndex * 100}%, 0)` }}
                >
                    {moments.map((moment, index) => {
                        const momentId = moment.moment_id || moment.content_id;
                        return (
                            <MomentSlide
                                key={momentId}
                                moment={moment}
                                isActive={index === activeIndex}
                                onNext={goNext}
                                onPrevious={goPrev}
                                onMomentChange={updateMoment}
                                onDeleteMoment={removeMoment}
                                onEditMoment={() => navigate(`/moments/${momentId}/edit`)}
                                onOpenComments={() => setCommentsMomentId(momentId)}
                            />
                        );
                    })}
                </div>
            </div>

            <button
                type="button"
                className="moments-nav-button next"
                onClick={goNext}
                disabled={activeIndex >= moments.length - 1 && !hasMore}
                aria-label="Next Moment"
            >
                <ChevronIcon direction="down" />
            </button>

            {commentsMomentId && (
                <div className="moments-comments-layer">
                    <button
                        type="button"
                        className="moments-comments-backdrop"
                        onClick={() => setCommentsMomentId(null)}
                        aria-label="Close comments"
                    />
                    <aside className="moments-comments-shell" role="dialog" aria-label="Moment comments">
                        <header className="moments-comments-header">
                            <h2>Comments</h2>
                            <button
                                type="button"
                                className="moments-comments-close"
                                onClick={() => setCommentsMomentId(null)}
                                aria-label="Close comments"
                            >
                                <CloseIcon />
                            </button>
                        </header>
                        <CommentSection
                            contentId={commentsMomentId}
                            isEnabled
                            onCommentsCountChange={(delta) => updateMoment(commentsMomentId, {
                                comments_count: Math.max(
                                    0,
                                    (moments.find((item) => (item.moment_id || item.content_id) === commentsMomentId)?.comments_count || 0) + delta,
                                ),
                            })}
                        />
                    </aside>
                </div>
            )}

            {isLoadingMore && <div className="moments-loading-more">Loading more</div>}
        </div>
    );
}


export function MomentSlide({
    moment,
    isActive,
    onNext,
    onPrevious,
    onMomentChange,
    onDeleteMoment,
    onEditMoment,
    onOpenComments,
}) {
    const { store } = useContext(StoreContext);
    const sessionIdRef = useRef(null);
    const isStartingSessionRef = useRef(false);
    const lastSentSecondRef = useRef(0);
    const lastCurrentTimeRef = useRef(0);
    const watchedSecondsRef = useRef(0);
    const optionsRef = useRef(null);
    const [actionError, setActionError] = useState("");
    const [isOptionsOpen, setIsOptionsOpen] = useState(false);

    const momentId = moment.moment_id || moment.content_id;
    const sources = useMemo(() => moment.playback_sources || [], [moment.playback_sources]);
    const posterUrl = moment.cover?.poster_url || moment.cover?.preview_url || moment.cover?.original_url || "";
    const authorName = moment.user?.username || "Unknown";

    useEffect(() => {
        sessionIdRef.current = null;
        isStartingSessionRef.current = false;
        lastSentSecondRef.current = 0;
        lastCurrentTimeRef.current = 0;
        watchedSecondsRef.current = 0;
    }, [momentId]);

    useEffect(() => {
        if (!isOptionsOpen) {
            return undefined;
        }
        const handlePointerDown = (event) => {
            if (optionsRef.current && !optionsRef.current.contains(event.target)) {
                setIsOptionsOpen(false);
            }
        };
        window.addEventListener("pointerdown", handlePointerDown);
        return () => window.removeEventListener("pointerdown", handlePointerDown);
    }, [isOptionsOpen]);

    const ensureViewSession = useCallback(async (initialPositionSeconds = 0) => {
        if (!store.isAuthenticated || !isActive || sessionIdRef.current || isStartingSessionRef.current) {
            return sessionIdRef.current;
        }
        isStartingSessionRef.current = true;
        try {
            const res = await ContentService.startViewSession(momentId, {
                source: "moments_feed",
                initial_position_seconds: Math.floor(initialPositionSeconds || 0),
                metadata: { surface: "videos_tab_moments" },
            });
            sessionIdRef.current = res.data.view_session_id;
            return sessionIdRef.current;
        } catch {
            return null;
        } finally {
            isStartingSessionRef.current = false;
        }
    }, [isActive, momentId, store.isAuthenticated]);

    const sendHeartbeat = useCallback(async ({ currentTime, duration, ended = false }) => {
        if (!store.isAuthenticated || !isActive) {
            return;
        }
        const sessionId = sessionIdRef.current || await ensureViewSession(currentTime);
        if (!sessionId) {
            return;
        }
        const currentSecond = Math.floor(currentTime || 0);
        if (!ended && currentSecond <= lastSentSecondRef.current) {
            return;
        }
        lastSentSecondRef.current = currentSecond;
        try {
            await ContentService.heartbeatViewSession(momentId, sessionId, {
                position_seconds: currentSecond,
                duration_seconds: Math.floor(duration || moment.duration_seconds || 0),
                watched_seconds_delta: Math.max(0, Math.floor(watchedSecondsRef.current)),
                source: "moments_feed",
                metadata: { surface: "videos_tab_moments" },
                ended,
            });
            watchedSecondsRef.current = 0;
        } catch {
            // View sessions should not interrupt playback.
        }
    }, [ensureViewSession, isActive, moment.duration_seconds, momentId, store.isAuthenticated]);

    const handleTimeUpdate = useCallback((payload) => {
        if (!isActive) {
            return;
        }
        const currentTime = payload.currentTime || 0;
        const delta = Math.max(0, currentTime - lastCurrentTimeRef.current);
        if (delta > 0 && delta < 5) {
            watchedSecondsRef.current += delta;
        }
        lastCurrentTimeRef.current = currentTime;
        void sendHeartbeat({ currentTime, duration: payload.duration });
    }, [isActive, sendHeartbeat]);

    const handleEnded = useCallback((payload) => {
        void sendHeartbeat({
            currentTime: payload.currentTime || moment.duration_seconds || 0,
            duration: payload.duration || moment.duration_seconds || 0,
            ended: true,
        });
        onNext?.();
    }, [moment.duration_seconds, onNext, sendHeartbeat]);

    const handleReaction = async (reactionType) => {
        if (!store.isAuthenticated) {
            setActionError("Log in to react to Moments.");
            return;
        }
        setActionError("");
        try {
            const res = moment.my_reaction === reactionType
                ? await ContentService.removeReaction(momentId, reactionType)
                : await ContentService.setReaction(momentId, reactionType);
            onMomentChange(momentId, {
                likes_count: res.data.likes_count,
                dislikes_count: res.data.dislikes_count,
                my_reaction: res.data.my_reaction,
            });
        } catch (reactionError) {
            setActionError(reactionError?.response?.data?.detail || "Failed to update reaction.");
        }
    };

    const handleDelete = async () => {
        if (!window.confirm("Delete this Moment?")) {
            return;
        }
        setActionError("");
        try {
            await MomentService.deleteMoment(momentId);
            onDeleteMoment?.(momentId);
        } catch (deleteError) {
            setActionError(deleteError?.response?.data?.detail || "Failed to delete Moment.");
        }
    };

    return (
        <article className={isActive ? "moment-slide active" : "moment-slide"} data-testid="moment-slide" aria-hidden={!isActive}>
            <div className="moment-player-shell">
                <VideoPlayer
                    skin="moments"
                    sources={sources}
                    posterUrl={posterUrl}
                    title={`Moment by ${authorName}`}
                    autoPlay={isActive}
                    muted
                    preload={isActive ? "auto" : "metadata"}
                    onTimeUpdate={handleTimeUpdate}
                    onEnded={handleEnded}
                />
                <div className="moment-overlay">
                    <div className="moment-copy">
                        <strong>@{authorName}</strong>
                        {moment.caption && <p>{moment.caption}</p>}
                        {moment.tags?.length > 0 && (
                            <div className="moment-tags">
                                {moment.tags.map((tag) => (
                                    <span key={tag.tag_id || tag.slug}>#{tag.slug || tag.name}</span>
                                ))}
                            </div>
                        )}
                    </div>
                    <div className="moment-actions" aria-label="Moment actions">
                        {
                            moment.is_owner &&
                            <div className="moment-options" ref={optionsRef}>
                                <button
                                    type="button"
                                    onClick={() => setIsOptionsOpen((value) => !value)}
                                    aria-label="Moment options"
                                >
                                    <OptionsIcon />
                                </button>
                                {
                                    isOptionsOpen &&
                                    <div className="moment-options-menu">
                                        <button type="button" onClick={onEditMoment}>
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
                        <button
                            type="button"
                            className={moment.my_reaction === "like" ? "active" : ""}
                            onClick={() => { void handleReaction("like"); }}
                            aria-label="Like Moment"
                        >
                            <LikeIcon />
                            <span>{moment.likes_count || 0}</span>
                        </button>
                        <button
                            type="button"
                            className={moment.my_reaction === "dislike" ? "active" : ""}
                            onClick={() => { void handleReaction("dislike"); }}
                            aria-label="Dislike Moment"
                        >
                            <DislikeIcon />
                            <span>{moment.dislikes_count || 0}</span>
                        </button>
                        <button
                            type="button"
                            onClick={onOpenComments}
                            aria-label="Open Moment comments"
                        >
                            <CommentIcon />
                            <span>{moment.comments_count || 0}</span>
                        </button>
                    </div>
                </div>
                {actionError && <div className="moment-action-error">{actionError}</div>}
            </div>
            <div className="moment-swipe-buttons">
                <button type="button" onClick={onPrevious}><ChevronIcon direction="up" />Previous</button>
                <button type="button" onClick={onNext}>Next<ChevronIcon direction="down" /></button>
            </div>
        </article>
    );
}


export default MomentsViewer;
