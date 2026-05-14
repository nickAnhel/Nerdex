import { useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import "./ArticleDetails.css";

import { StoreContext } from "../..";
import ArticleService from "../../service/ArticleService";
import ContentService from "../../service/ContentService";

import Loader from "../../components/loader/Loader";
import Modal from "../../components/modal/Modal";
import CommentSection from "../../components/comment-section/CommentSection";
import ArticleRenderer from "../../components/article-renderer/ArticleRenderer";
import TagChip from "../../components/tag-chip/TagChip";
import CommentIcon from "../../components/icons/CommentIcon";
import DislikeIcon from "../../components/icons/DislikeIcon";
import LikeIcon from "../../components/icons/LikeIcon";
import { CopyIcon, EditIcon, ShareIcon, TrashIcon } from "../../components/icons/ArticleUiIcons";
import { getAvatarUrl } from "../../utils/avatar";
import { stripArticleFormatting } from "../../utils/articleMarkdown";

function ArticleDetails() {
    const { store } = useContext(StoreContext);
    const navigate = useNavigate();
    const { articleId } = useParams();
    const pageRef = useRef(null);
    const commentsRef = useRef(null);
    const viewSessionIdRef = useRef(null);
    const viewSessionPromiseRef = useRef(null);
    const heartbeatInFlightRef = useRef(false);
    const pendingHeartbeatRef = useRef(false);
    const heartbeatTimerRef = useRef(null);
    const latestReadingProgressRef = useRef(0);
    const lastSentProgressRef = useRef(0);
    const readSecondsAccumulatorRef = useRef(0);
    const lastReadTickRef = useRef(null);

    const [article, setArticle] = useState(null);
    const [isLoading, setIsLoading] = useState(true);
    const [isUnavailable, setIsUnavailable] = useState(false);
    const [readingProgress, setReadingProgress] = useState(0);
    const [avatarSrc, setAvatarSrc] = useState("");
    const [isDeleting, setIsDeleting] = useState(false);
    const [isDeleteModalActive, setIsDeleteModalActive] = useState(false);
    const [isShareModalActive, setIsShareModalActive] = useState(false);
    const [copyState, setCopyState] = useState("Copy link");

    useEffect(() => {
        if (!articleId) {
            return;
        }
        viewSessionIdRef.current = null;
        viewSessionPromiseRef.current = null;
        heartbeatInFlightRef.current = false;
        pendingHeartbeatRef.current = false;
        latestReadingProgressRef.current = 0;
        lastSentProgressRef.current = 0;
        readSecondsAccumulatorRef.current = 0;
        lastReadTickRef.current = null;

        const fetchArticle = async () => {
            setIsLoading(true);
            setIsUnavailable(false);
            try {
                const res = await ArticleService.getArticle(articleId);
                setArticle(res.data);
                setAvatarSrc(getAvatarUrl(res.data.user, "small"));
            } catch (error) {
                console.log(error);
                setArticle(null);
                setIsUnavailable(true);
            } finally {
                setIsLoading(false);
            }
        };

        fetchArticle();
    }, [articleId]);

    useEffect(() => {
        if (!isShareModalActive) {
            setCopyState("Copy link");
        }
    }, [isShareModalActive]);

    useEffect(() => {
        const pageNode = pageRef.current;
        if (!pageNode) {
            return undefined;
        }

        const handleScroll = () => {
            const top = pageNode.scrollTop;
            const height = pageNode.scrollHeight - pageNode.clientHeight;
            const ratio = height > 0 ? Math.min(100, Math.max(0, (top / height) * 100)) : 0;
            latestReadingProgressRef.current = ratio;
            setReadingProgress(ratio);
        };

        pageNode.addEventListener("scroll", handleScroll);
        handleScroll();
        return () => pageNode.removeEventListener("scroll", handleScroll);
    }, [isLoading, isUnavailable, article?.article_id]);

    const ensureViewSession = useCallback(async () => {
        if (!store.isAuthenticated || !article?.article_id) {
            return null;
        }
        if (viewSessionIdRef.current) {
            return viewSessionIdRef.current;
        }
        if (!viewSessionPromiseRef.current) {
            viewSessionPromiseRef.current = ContentService.startViewSession(article.article_id, {
                source: "article_detail",
                initial_progress_percent: Math.floor(latestReadingProgressRef.current || 0),
                metadata: { surface: "article_details" },
            })
                .then((res) => {
                    viewSessionIdRef.current = res.data.view_session_id;
                    lastSentProgressRef.current = Math.max(
                        lastSentProgressRef.current,
                        res.data.progress_percent || 0,
                    );
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
    }, [article?.article_id, store.isAuthenticated]);

    const sendArticleHeartbeat = useCallback(async ({ ended = false } = {}) => {
        if (!store.isAuthenticated || !article?.article_id) {
            return;
        }
        if (heartbeatInFlightRef.current) {
            pendingHeartbeatRef.current = true;
            return;
        }

        heartbeatInFlightRef.current = true;
        let consumedReadSeconds = 0;
        try {
            const sessionId = await ensureViewSession();
            if (!sessionId) {
                return;
            }

            const progressPercent = Math.floor(latestReadingProgressRef.current || 0);
            const readSecondsDelta = Math.floor(readSecondsAccumulatorRef.current);
            if (
                !ended
                && readSecondsDelta <= 0
                && progressPercent <= lastSentProgressRef.current
            ) {
                return;
            }

            consumedReadSeconds = readSecondsDelta;
            readSecondsAccumulatorRef.current = Math.max(0, readSecondsAccumulatorRef.current - readSecondsDelta);
            const payload = {
                progress_percent: progressPercent,
                watched_seconds_delta: readSecondsDelta,
                source: "article_detail",
                metadata: { surface: "article_details" },
                ended,
            };
            const res = ended
                ? await ContentService.finishViewSession(article.article_id, sessionId, payload)
                : await ContentService.heartbeatViewSession(article.article_id, sessionId, payload);
            lastSentProgressRef.current = Math.max(
                lastSentProgressRef.current,
                res.data.progress_percent || progressPercent,
            );
        } catch (error) {
            readSecondsAccumulatorRef.current += consumedReadSeconds;
            console.log(error);
        } finally {
            heartbeatInFlightRef.current = false;
            if (pendingHeartbeatRef.current) {
                pendingHeartbeatRef.current = false;
                window.setTimeout(() => {
                    void sendArticleHeartbeat();
                }, 0);
            }
        }
    }, [article?.article_id, ensureViewSession, store.isAuthenticated]);

    const scheduleArticleHeartbeat = useCallback(() => {
        if (heartbeatTimerRef.current) {
            return;
        }
        heartbeatTimerRef.current = window.setTimeout(() => {
            heartbeatTimerRef.current = null;
            void sendArticleHeartbeat();
        }, 1500);
    }, [sendArticleHeartbeat]);

    useEffect(() => {
        if (!store.isAuthenticated || !article?.article_id || article.status !== "published") {
            return undefined;
        }

        void ensureViewSession();
        lastReadTickRef.current = Date.now();

        const tickReadTime = () => {
            const now = Date.now();
            const previous = lastReadTickRef.current || now;
            lastReadTickRef.current = now;
            if (document.visibilityState !== "visible") {
                return;
            }
            const deltaSeconds = Math.max(0, Math.min(5, (now - previous) / 1000));
            readSecondsAccumulatorRef.current += deltaSeconds;
            if (readSecondsAccumulatorRef.current >= 10) {
                scheduleArticleHeartbeat();
            }
        };

        const intervalId = window.setInterval(tickReadTime, 1000);
        const handleVisibilityChange = () => {
            tickReadTime();
        };
        const handlePageHide = () => {
            tickReadTime();
            void sendArticleHeartbeat({ ended: true });
        };
        document.addEventListener("visibilitychange", handleVisibilityChange);
        window.addEventListener("pagehide", handlePageHide);

        return () => {
            tickReadTime();
            window.clearInterval(intervalId);
            document.removeEventListener("visibilitychange", handleVisibilityChange);
            window.removeEventListener("pagehide", handlePageHide);
            if (heartbeatTimerRef.current) {
                window.clearTimeout(heartbeatTimerRef.current);
                heartbeatTimerRef.current = null;
            }
            void sendArticleHeartbeat({ ended: true });
        };
    }, [
        article?.article_id,
        article?.status,
        ensureViewSession,
        scheduleArticleHeartbeat,
        sendArticleHeartbeat,
        store.isAuthenticated,
    ]);

    useEffect(() => {
        if (!store.isAuthenticated || !article?.article_id || article.status !== "published") {
            return;
        }
        const progressPercent = Math.floor(readingProgress || 0);
        if (progressPercent >= lastSentProgressRef.current + 5) {
            scheduleArticleHeartbeat();
        }
    }, [
        article?.article_id,
        article?.status,
        readingProgress,
        scheduleArticleHeartbeat,
        store.isAuthenticated,
    ]);

    const canReact = store.isAuthenticated && article?.status === "published";
    const isLiked = article?.my_reaction === "like";
    const isDisliked = article?.my_reaction === "dislike";

    const tocItems = useMemo(() => article?.toc || [], [article]);

    const handleLike = async () => {
        if (!article) {
            return;
        }
        const res = isLiked
            ? await ArticleService.unlikeArticle(article.article_id)
            : await ArticleService.likeArticle(article.article_id);
        setArticle((prevArticle) => ({
            ...prevArticle,
            likes_count: res.data.likes_count,
            dislikes_count: res.data.dislikes_count,
            my_reaction: res.data.my_reaction,
        }));
    };

    const handleDislike = async () => {
        if (!article) {
            return;
        }
        const res = isDisliked
            ? await ArticleService.undislikeArticle(article.article_id)
            : await ArticleService.dislikeArticle(article.article_id);
        setArticle((prevArticle) => ({
            ...prevArticle,
            likes_count: res.data.likes_count,
            dislikes_count: res.data.dislikes_count,
            my_reaction: res.data.my_reaction,
        }));
    };

    const handleCommentsCountChange = (delta) => {
        setArticle((prevArticle) => (
            prevArticle
                ? {
                    ...prevArticle,
                    comments_count: Math.max(0, prevArticle.comments_count + delta),
                }
                : prevArticle
        ));
    };

    const handleDelete = async () => {
        if (!article || isDeleting) {
            return;
        }

        setIsDeleting(true);
        try {
            await ArticleService.deleteArticle(article.article_id);
            store.refreshPosts();
            navigate("/articles", { replace: true });
        } catch (error) {
            console.log(error);
        } finally {
            setIsDeleting(false);
        }
    };

    const handleScrollToComments = () => {
        commentsRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    };

    const handleTocClick = (event, anchor) => {
        event.preventDefault();
        document.getElementById(anchor)?.scrollIntoView({ behavior: "smooth", block: "start" });
    };

    const handleCopyLink = async () => {
        try {
            await navigator.clipboard.writeText(`${window.location.origin}${article.canonical_path}`);
            setCopyState("Copied");
            window.setTimeout(() => setCopyState("Copy link"), 1600);
        } catch (error) {
            console.log(error);
            setCopyState("Copy failed");
            window.setTimeout(() => setCopyState("Copy link"), 1600);
        }
    };

    if (isLoading) {
        return (
            <div id="article-details" className="article-details-state" ref={pageRef}>
                <Loader />
            </div>
        );
    }

    if (isUnavailable || !article) {
        return (
            <div id="article-details" className="article-details-state" ref={pageRef}>
                <h2>Article unavailable</h2>
                <p>This article is private, still a draft, deleted, or does not exist.</p>
            </div>
        );
    }

    return (
        <div id="article-details" ref={pageRef}>
            <div className="article-reading-progress" style={{ width: `${readingProgress}%` }} />

            <div className="article-details-layout">
                <main className="article-details-main">
                    <header className="article-hero">
                        <div className="article-hero-meta">
                            <Link to={`/people/@${article.user.username}`} className="article-author-link">
                                <img
                                    src={avatarSrc}
                                    alt={`${article.user.username} profile`}
                                    onError={() => setAvatarSrc("/assets/profile.svg")}
                                />
                                <span>{article.user.username}</span>
                            </Link>
                            <span>{new Date(article.published_at || article.created_at).toLocaleDateString()}</span>
                            <span>{article.reading_time_minutes} min read</span>
                            {
                                article.updated_at !== article.created_at &&
                                <span>Updated {new Date(article.updated_at).toLocaleDateString()}</span>
                            }
                        </div>

                        <h1>{article.title}</h1>
                        {
                            article.excerpt &&
                            <p className="article-hero-excerpt">{stripArticleFormatting(article.excerpt)}</p>
                        }

                        {
                            article.tags?.length > 0 &&
                            <div className="article-hero-tags">
                                {article.tags.map((tag) => <TagChip key={tag.tag_id || tag.slug} slug={tag.slug} />)}
                            </div>
                        }

                        {
                            article.cover?.original_url &&
                            <div className="article-hero-cover">
                                <img src={article.cover.original_url} alt={article.title} />
                            </div>
                        }
                    </header>

                    <section className="article-body">
                        <ArticleRenderer bodyMarkdown={article.body_markdown} article={article} />
                    </section>

                    <section className="article-feedback">
                        <button type="button" onClick={handleLike} className={isLiked ? "active" : ""} disabled={!canReact}>
                            <LikeIcon />
                            <span>{article.likes_count}</span>
                        </button>
                        <button type="button" onClick={handleDislike} className={isDisliked ? "active" : ""} disabled={!canReact}>
                            <DislikeIcon />
                            <span>{article.dislikes_count}</span>
                        </button>
                        <button type="button" onClick={handleScrollToComments}>
                            <CommentIcon />
                            <span>{article.comments_count}</span>
                        </button>
                        <button type="button" onClick={() => setIsShareModalActive(true)}>
                            <ShareIcon />
                            <span>Share</span>
                        </button>
                        {
                            article.is_owner &&
                            <>
                                <button type="button" onClick={() => navigate(`/articles/${article.article_id}/edit`)}>
                                    <EditIcon />
                                    <span>Edit</span>
                                </button>
                                <button
                                    type="button"
                                    className="danger"
                                    onClick={() => setIsDeleteModalActive(true)}
                                    disabled={isDeleting}
                                >
                                    <TrashIcon />
                                    <span>Delete</span>
                                </button>
                            </>
                        }
                    </section>

                    <section className="article-comments" ref={commentsRef}>
                        <CommentSection
                            contentId={article.article_id}
                            isEnabled={article.status === "published"}
                            onCommentsCountChange={handleCommentsCountChange}
                        />
                    </section>
                </main>

                <aside className="article-details-sidebar">
                    <div className="article-toc-card">
                        <div className="article-toc-title">Contents</div>
                        {
                            tocItems.length === 0
                                ? <div className="article-toc-empty">No headings yet.</div>
                                : (
                                    <nav className="article-toc-nav">
                                        {
                                            tocItems.map((item) => (
                                                <a
                                                    key={`${item.anchor}-${item.level}`}
                                                    href={`#${item.anchor}`}
                                                    className={`level-${item.level}`}
                                                    onClick={(event) => handleTocClick(event, item.anchor)}
                                                >
                                                    {item.text}
                                                </a>
                                            ))
                                        }
                                    </nav>
                                )
                        }
                    </div>
                </aside>
            </div>

            <Modal
                active={isDeleteModalActive}
                setActive={() => {
                    if (!isDeleting) {
                        setIsDeleteModalActive(false);
                    }
                }}
            >
                <div className="delete-post-modal">
                    <h2>Delete article?</h2>
                    <p>This action will hide the article from regular lists. You can&apos;t undo it from the interface.</p>
                    <div className="delete-post-modal-actions">
                        <button
                            type="button"
                            className="btn btn-secondary"
                            onClick={() => setIsDeleteModalActive(false)}
                            disabled={isDeleting}
                        >
                            Cancel
                        </button>
                        <button
                            type="button"
                            className="btn btn-danger"
                            onClick={handleDelete}
                            disabled={isDeleting}
                        >
                            {isDeleting ? <Loader /> : "Delete"}
                        </button>
                    </div>
                </div>
            </Modal>

            <Modal active={isShareModalActive} setActive={setIsShareModalActive}>
                <div className="article-share-modal">
                    <h2>Share article</h2>
                    <p>Copy the article link. Internal messenger sharing can be added here later.</p>
                    <div className="article-share-link-row">
                        <div className="article-share-link-box">
                            {`${window.location.origin}${article.canonical_path}`}
                        </div>
                        <button type="button" className="btn btn-primary article-share-copy-button" onClick={handleCopyLink}>
                            <CopyIcon />
                            <span>{copyState}</span>
                        </button>
                    </div>
                </div>
            </Modal>
        </div>
    );
}

export default ArticleDetails;
