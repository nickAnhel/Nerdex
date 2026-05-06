import { useCallback, useContext, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import "./VideoDetails.css";

import { StoreContext } from "../..";
import CommentSection from "../../components/comment-section/CommentSection";
import CommentIcon from "../../components/icons/CommentIcon";
import DislikeIcon from "../../components/icons/DislikeIcon";
import LikeIcon from "../../components/icons/LikeIcon";
import Loader from "../../components/loader/Loader";
import Modal from "../../components/modal/Modal";
import TagChip from "../../components/tag-chip/TagChip";
import VideoPlayer from "../../components/video-player/VideoPlayer";
import ContentService from "../../service/ContentService";
import VideoService from "../../service/VideoService";
import { getAvatarUrl } from "../../utils/avatar";
import { formatDuration } from "../../components/video-card/VideoCard";


function VideoDetails() {
    const { store } = useContext(StoreContext);
    const navigate = useNavigate();
    const { videoId } = useParams();
    const [video, setVideo] = useState(null);
    const [isLoading, setIsLoading] = useState(true);
    const [isUnavailable, setIsUnavailable] = useState(false);
    const [avatarSrc, setAvatarSrc] = useState("");
    const [isDeleteModalActive, setIsDeleteModalActive] = useState(false);
    const [isDeleting, setIsDeleting] = useState(false);
    const viewSessionIdRef = useRef(null);
    const viewSessionPromiseRef = useRef(null);
    const latestPlaybackRef = useRef({ currentTime: 0, duration: 0 });
    const isPlayingRef = useRef(false);
    const commentsRef = useRef(null);

    const fetchVideo = useCallback(async ({ showLoader = false } = {}) => {
        if (showLoader) {
            setIsLoading(true);
        }
        setIsUnavailable(false);
        try {
            const res = await VideoService.getVideo(videoId);
            setVideo(res.data);
            setAvatarSrc(getAvatarUrl(res.data.user, "small"));
        } catch (error) {
            console.log(error);
            setVideo(null);
            setIsUnavailable(true);
        } finally {
            if (showLoader) {
                setIsLoading(false);
            }
        }
    }, [videoId]);

    useEffect(() => {
        if (videoId) {
            viewSessionIdRef.current = null;
            viewSessionPromiseRef.current = null;
            void fetchVideo({ showLoader: true });
        }
    }, [fetchVideo, videoId]);

    useEffect(() => {
        if (!video || ["ready", "failed"].includes(video.processing_status)) {
            return undefined;
        }
        const intervalId = window.setInterval(() => {
            void fetchVideo();
        }, 5000);
        return () => window.clearInterval(intervalId);
    }, [fetchVideo, video]);

    const handleCommentsCountChange = (delta) => {
        setVideo((prevVideo) => (
            prevVideo
                ? { ...prevVideo, comments_count: Math.max(0, prevVideo.comments_count + delta) }
                : prevVideo
        ));
    };

    const handleDelete = async () => {
        if (!video || isDeleting) {
            return;
        }
        setIsDeleting(true);
        try {
            await VideoService.deleteVideo(video.video_id);
            store.refreshPosts();
            navigate("/videos", { replace: true });
        } catch (error) {
            console.log(error);
        } finally {
            setIsDeleting(false);
        }
    };

    const canReact = store.isAuthenticated && video?.status === "published" && video?.processing_status === "ready";
    const isLiked = video?.my_reaction === "like";
    const isDisliked = video?.my_reaction === "dislike";

    const handleLike = async () => {
        if (!video?.content_id) {
            return;
        }
        const res = isLiked
            ? await ContentService.removeReaction(video.content_id, "like")
            : await ContentService.setReaction(video.content_id, "like");
        setVideo((prevVideo) => (
            prevVideo
                ? {
                    ...prevVideo,
                    likes_count: res.data.likes_count,
                    dislikes_count: res.data.dislikes_count,
                    my_reaction: res.data.my_reaction,
                }
                : prevVideo
        ));
    };

    const handleDislike = async () => {
        if (!video?.content_id) {
            return;
        }
        const res = isDisliked
            ? await ContentService.removeReaction(video.content_id, "dislike")
            : await ContentService.setReaction(video.content_id, "dislike");
        setVideo((prevVideo) => (
            prevVideo
                ? {
                    ...prevVideo,
                    likes_count: res.data.likes_count,
                    dislikes_count: res.data.dislikes_count,
                    my_reaction: res.data.my_reaction,
                }
                : prevVideo
        ));
    };

    const handleScrollToComments = () => {
        commentsRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    };

    const applyViewSessionResponse = useCallback((data) => {
        setVideo((prevVideo) => (
            prevVideo
                ? {
                    ...prevVideo,
                    history_progress: data,
                    views_count: data.views_count ?? prevVideo.views_count,
                }
                : prevVideo
        ));
    }, []);

    const ensureViewSession = useCallback(async (payload = latestPlaybackRef.current) => {
        if (!store.isAuthenticated || !video?.content_id) {
            return null;
        }
        if (viewSessionIdRef.current) {
            return viewSessionIdRef.current;
        }
        if (!viewSessionPromiseRef.current) {
            viewSessionPromiseRef.current = ContentService.startViewSession(video.content_id, {
                source: "video_detail",
                initial_position_seconds: Math.floor(payload.currentTime || 0),
                metadata: {},
            })
                .then((res) => {
                    viewSessionIdRef.current = res.data.view_session_id;
                    applyViewSessionResponse(res.data);
                    return res.data.view_session_id;
                })
                .catch((error) => {
                    console.log(error);
                    return null;
                })
                .finally(() => {
                    viewSessionPromiseRef.current = null;
                });
        }
        return viewSessionPromiseRef.current;
    }, [applyViewSessionResponse, store.isAuthenticated, video?.content_id]);

    const heartbeatViewSession = useCallback(async ({ ended = false, watchedSecondsDelta = 0, ensureSession = true } = {}) => {
        if (!store.isAuthenticated || !video?.content_id) {
            return;
        }
        try {
            const sessionId = ensureSession
                ? await ensureViewSession()
                : viewSessionIdRef.current;
            if (!sessionId) {
                return;
            }
            const payload = {
                position_seconds: Math.floor(latestPlaybackRef.current.currentTime || 0),
                duration_seconds: Math.floor(latestPlaybackRef.current.duration || video.duration_seconds || 0),
                watched_seconds_delta: watchedSecondsDelta,
                source: "video_detail",
                metadata: {},
                ended,
            };
            const res = ended
                ? await ContentService.finishViewSession(video.content_id, sessionId, payload)
                : await ContentService.heartbeatViewSession(video.content_id, sessionId, payload);
            applyViewSessionResponse(res.data);
        } catch (error) {
            console.log(error);
        }
    }, [applyViewSessionResponse, ensureViewSession, store.isAuthenticated, video?.content_id, video?.duration_seconds]);

    const handlePlayerPlay = (payload) => {
        latestPlaybackRef.current = payload;
        isPlayingRef.current = true;
        void ensureViewSession(payload);
    };

    const handlePlayerPause = (payload) => {
        latestPlaybackRef.current = payload;
        isPlayingRef.current = false;
        void heartbeatViewSession();
    };

    const handlePlayerEnded = (payload) => {
        latestPlaybackRef.current = payload;
        isPlayingRef.current = false;
        void heartbeatViewSession({ ended: true });
    };

    const handlePlayerTimeUpdate = (payload) => {
        latestPlaybackRef.current = payload;
    };

    useEffect(() => {
        if (!store.isAuthenticated || !video?.content_id) {
            return undefined;
        }
        const intervalId = window.setInterval(() => {
            if (isPlayingRef.current) {
                void heartbeatViewSession({ watchedSecondsDelta: 10 });
            }
        }, 10000);
        const handleUnload = () => {
            if (isPlayingRef.current) {
                void heartbeatViewSession();
            }
        };
        window.addEventListener("beforeunload", handleUnload);
        return () => {
            window.clearInterval(intervalId);
            window.removeEventListener("beforeunload", handleUnload);
        };
    }, [heartbeatViewSession, store.isAuthenticated, video?.content_id]);

    if (isLoading) {
        return <div className="video-details-state"><Loader /></div>;
    }

    if (isUnavailable || !video) {
        return (
            <div className="video-details-state">
                <h2>Video unavailable</h2>
                <p>This video is private, processing, deleted, or does not exist.</p>
            </div>
        );
    }

    const ready = video.processing_status === "ready";
    const canShowPlayer = ready && video.playback_sources?.length > 0;

    return (
        <main className="video-details-page">
            <section className="video-watch-surface">
                {
                    canShowPlayer
                        ? (
                            <VideoPlayer
                                skin="page"
                                sources={video.playback_sources}
                                posterUrl={video.cover?.preview_url || video.cover?.original_url}
                                title={video.title}
                                chapters={video.chapters || []}
                                initialTimeSeconds={video.history_progress?.progress_percent < 95 ? video.history_progress?.last_position_seconds : 0}
                                preload="metadata"
                                onPlay={handlePlayerPlay}
                                onPause={handlePlayerPause}
                                onEnded={handlePlayerEnded}
                                onTimeUpdate={handlePlayerTimeUpdate}
                            />
                        )
                        : (
                            <div className="video-processing-panel">
                                {
                                    video.cover?.preview_url &&
                                    <img src={video.cover.preview_url} alt={video.title || "Video cover"} />
                                }
                                <div>
                                    <h2>{ready ? "Playback unavailable" : "Video is processing"}</h2>
                                    <p>{video.processing_error || `Current status: ${video.processing_status}`}</p>
                                </div>
                            </div>
                        )
                }
            </section>

            <section className="video-details-main">
                <div className="video-details-meta-row">
                    <Link to={`/people/@${video.user.username}`} className="video-details-author">
                        <img
                            src={avatarSrc}
                            alt={`${video.user.username} profile`}
                            onError={() => setAvatarSrc("/assets/profile.svg")}
                        />
                        <span>{video.user.username}</span>
                    </Link>
                    <span>{new Date(video.published_at || video.created_at).toLocaleDateString()}</span>
                    {
                        video.duration_seconds &&
                        <span>{formatDuration(video.duration_seconds)}</span>
                    }
                </div>

                <div className="video-details-title-row">
                    <h1>{video.title || "Untitled video"}</h1>
                    {
                        video.is_owner &&
                        <div className="video-owner-actions">
                            <button type="button" onClick={() => navigate(`/videos/${video.video_id}/edit`)}>
                                Edit
                            </button>
                            <button type="button" onClick={() => setIsDeleteModalActive(true)}>
                                Delete
                            </button>
                        </div>
                    }
                </div>

                <div className="video-details-badges">
                    {
                        video.status === "draft" &&
                        <span>Draft</span>
                    }
                    {
                        video.visibility === "private" &&
                        <span>Private</span>
                    }
                    <span>{video.processing_status}</span>
                </div>

                <div className="video-details-feedback" aria-label="Video feedback">
                    <div className="video-details-views">
                        <ViewIcon />
                        <span>{video.views_count || 0} views</span>
                    </div>
                    <button type="button" onClick={handleLike} className={isLiked ? "active" : ""} disabled={!canReact}>
                        <LikeIcon />
                        <span>{video.likes_count || 0}</span>
                    </button>
                    <button type="button" onClick={handleDislike} className={isDisliked ? "active" : ""} disabled={!canReact}>
                        <DislikeIcon />
                        <span>{video.dislikes_count || 0}</span>
                    </button>
                    <button type="button" onClick={handleScrollToComments}>
                        <CommentIcon />
                        <span>{video.comments_count || 0}</span>
                    </button>
                </div>

                {
                    video.description &&
                    <p className="video-details-description">{video.description}</p>
                }

                {
                    video.tags?.length > 0 &&
                    <div className="video-details-tags">
                        {video.tags.map((tag) => <TagChip key={tag.tag_id || tag.slug} slug={tag.slug} />)}
                    </div>
                }
            </section>

            <section ref={commentsRef}>
                <CommentSection
                    contentId={video.content_id}
                    isEnabled={video.status === "published" && ready}
                    onCommentsCountChange={handleCommentsCountChange}
                />
            </section>

            <Modal
                active={isDeleteModalActive}
                setActive={() => {
                    if (!isDeleting) {
                        setIsDeleteModalActive(false);
                    }
                }}
            >
                <div className="video-delete-modal">
                    <h2>Delete video?</h2>
                    <p>This will remove the video from regular lists and playback pages.</p>
                    <div className="video-delete-modal-actions">
                        <button
                            type="button"
                            className="secondary"
                            onClick={() => setIsDeleteModalActive(false)}
                            disabled={isDeleting}
                        >
                            Cancel
                        </button>
                        <button
                            type="button"
                            className="danger"
                            onClick={handleDelete}
                            disabled={isDeleting}
                        >
                            {isDeleting ? "Deleting..." : "Delete"}
                        </button>
                    </div>
                </div>
            </Modal>
        </main>
    );
}

function ViewIcon() {
    return (
        <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
            <path
                d="M12 5c5 0 8.5 4.2 9.6 6.1a1.8 1.8 0 0 1 0 1.8C20.5 14.8 17 19 12 19s-8.5-4.2-9.6-6.1a1.8 1.8 0 0 1 0-1.8C3.5 9.2 7 5 12 5Zm0 2C7.9 7 5 10.5 4.2 12c.8 1.5 3.7 5 7.8 5s7-3.5 7.8-5C19 10.5 16.1 7 12 7Zm0 2a3 3 0 1 1 0 6 3 3 0 0 1 0-6Z"
                fill="currentColor"
            />
        </svg>
    );
}

export default VideoDetails;
