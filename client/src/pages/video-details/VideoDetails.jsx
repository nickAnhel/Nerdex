import { useContext, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import "./VideoDetails.css";

import { StoreContext } from "../..";
import CommentSection from "../../components/comment-section/CommentSection";
import Loader from "../../components/loader/Loader";
import TagChip from "../../components/tag-chip/TagChip";
import VideoPlayer from "../../components/video-player/VideoPlayer";
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

    useEffect(() => {
        const fetchVideo = async () => {
            setIsLoading(true);
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
                setIsLoading(false);
            }
        };
        if (videoId) {
            void fetchVideo();
        }
    }, [videoId]);

    const handleCommentsCountChange = (delta) => {
        setVideo((prevVideo) => (
            prevVideo
                ? { ...prevVideo, comments_count: Math.max(0, prevVideo.comments_count + delta) }
                : prevVideo
        ));
    };

    const handleDelete = async () => {
        await VideoService.deleteVideo(video.video_id);
        store.refreshPosts();
        navigate("/videos", { replace: true });
    };

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
                                preload="metadata"
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
                            <button type="button" onClick={handleDelete}>
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

            <CommentSection
                contentId={video.content_id}
                isEnabled={video.status === "published" && ready}
                onCommentsCountChange={handleCommentsCountChange}
            />
        </main>
    );
}

export default VideoDetails;
