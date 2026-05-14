import { useCallback, useContext, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import "./Activity.css";

import { StoreContext } from "../..";
import ActivityService from "../../service/ActivityService";
import FeedContentCard from "../../components/feed-content-card/FeedContentCard";
import Loader from "../../components/loader/Loader";
import Unauthorized from "../../components/unauthorized/Unauthorized";
import { getAvatarUrl } from "../../utils/avatar";


const ACTION_FILTERS = [
    { id: "all", label: "All", actionTypes: null },
    { id: "views", label: "Views", actionTypes: ["content_view"] },
    { id: "likes", label: "Likes", actionTypes: ["content_like"] },
    { id: "dislikes", label: "Dislikes", actionTypes: ["content_dislike"] },
    { id: "comments", label: "Comments", actionTypes: ["content_comment"] },
    { id: "follows", label: "Follows", actionTypes: ["user_follow", "user_unfollow"] },
];

const CONTENT_FILTERS = [
    { id: "all", label: "All", contentType: null },
    { id: "post", label: "Posts", contentType: "post" },
    { id: "article", label: "Articles", contentType: "article" },
    { id: "video", label: "Videos", contentType: "video" },
    { id: "moment", label: "Moments", contentType: "moment" },
    { id: "authors", label: "Authors", contentType: null },
];

const PERIOD_FILTERS = [
    { id: "week", label: "Week" },
    { id: "month", label: "Month" },
    { id: "year", label: "Year" },
    { id: "all_time", label: "All time" },
];

const PAGE_SIZE = 20;


function Activity() {
    const { store } = useContext(StoreContext);
    const [actionFilter, setActionFilter] = useState("all");
    const [contentFilter, setContentFilter] = useState("all");
    const [periodFilter, setPeriodFilter] = useState("week");
    const [items, setItems] = useState([]);
    const [offset, setOffset] = useState(0);
    const [hasMore, setHasMore] = useState(false);
    const [isLoading, setIsLoading] = useState(false);
    const [isLoadingMore, setIsLoadingMore] = useState(false);
    const [error, setError] = useState(null);
    const [reloadKey, setReloadKey] = useState(0);

    const queryParams = useMemo(() => {
        const action = ACTION_FILTERS.find((filter) => filter.id === actionFilter);
        const content = CONTENT_FILTERS.find((filter) => filter.id === contentFilter);
        const params = {
            period: periodFilter,
            offset,
            limit: PAGE_SIZE,
        };
        if (contentFilter === "authors") {
            params.action_type = ["user_follow", "user_unfollow"];
            return params;
        }
        if (action?.actionTypes) {
            params.action_type = action.actionTypes;
        }
        if (content?.contentType) {
            params.content_type = content.contentType;
        }
        return params;
    }, [actionFilter, contentFilter, offset, periodFilter]);

    useEffect(() => {
        setItems([]);
        setOffset(0);
        setHasMore(false);
    }, [actionFilter, contentFilter, periodFilter]);

    const loadActivity = useCallback(async () => {
        if (!store.isAuthenticated) {
            return;
        }
        setError(null);
        setIsLoading(offset === 0);
        setIsLoadingMore(offset > 0);
        try {
            const res = await ActivityService.getActivity(queryParams);
            setItems((prevItems) => (
                offset === 0
                    ? res.data.items
                    : [...prevItems, ...res.data.items]
            ));
            setHasMore(res.data.has_more);
        } catch (e) {
            setError(e);
        } finally {
            setIsLoading(false);
            setIsLoadingMore(false);
        }
    }, [offset, queryParams, store.isAuthenticated]);

    useEffect(() => {
        void loadActivity();
    }, [loadActivity, reloadKey]);

    if (!store.isAuthenticated) {
        return (
            <div id="activity-page">
                <Unauthorized />
            </div>
        );
    }

    const hasActiveFilters = actionFilter !== "all" || contentFilter !== "all" || periodFilter !== "all_time";

    return (
        <div id="activity-page">
            <div className="activity-shell">
                <header className="activity-header">
                    <div>
                        <h1>Activity</h1>
                    </div>
                    <button
                        type="button"
                        className="btn btn-outline-primary activity-retry"
                        onClick={() => setReloadKey((value) => value + 1)}
                    >
                        Retry
                    </button>
                </header>

                <ActivityFilters
                    actionFilter={actionFilter}
                    contentFilter={contentFilter}
                    periodFilter={periodFilter}
                    setActionFilter={setActionFilter}
                    setContentFilter={setContentFilter}
                    setPeriodFilter={setPeriodFilter}
                />

                {isLoading && (
                    <div className="activity-state">
                        <Loader />
                    </div>
                )}

                {!isLoading && error && (
                    <div className="activity-state">
                        <div className="activity-state-title">Activity could not be loaded</div>
                        <button
                            type="button"
                            className="btn btn-primary"
                            onClick={() => setReloadKey((value) => value + 1)}
                        >
                            Retry
                        </button>
                    </div>
                )}

                {!isLoading && !error && items.length === 0 && (
                    <div className="activity-state">
                        {hasActiveFilters ? "No activity matches these filters" : "No activity yet"}
                    </div>
                )}

                {!isLoading && !error && items.length > 0 && (
                    <div className="activity-list">
                        {items.map((event) => (
                            <ActivityEventCard key={event.activity_event_id} event={event} />
                        ))}
                    </div>
                )}

                {!isLoading && !error && hasMore && (
                    <button
                        type="button"
                        className="btn btn-outline-primary activity-load-more"
                        onClick={() => setOffset((value) => value + PAGE_SIZE)}
                        disabled={isLoadingMore}
                    >
                        {isLoadingMore ? <Loader /> : "Load more"}
                    </button>
                )}
            </div>
        </div>
    );
}


function ActivityFilters({
    actionFilter,
    contentFilter,
    periodFilter,
    setActionFilter,
    setContentFilter,
    setPeriodFilter,
}) {
    return (
        <div className="activity-filters">
            <FilterGroup label="Action">
                {ACTION_FILTERS.map((filter) => (
                    <FilterButton
                        key={filter.id}
                        active={actionFilter === filter.id}
                        onClick={() => setActionFilter(filter.id)}
                    >
                        {filter.label}
                    </FilterButton>
                ))}
            </FilterGroup>
            <FilterGroup label="Content">
                {CONTENT_FILTERS.map((filter) => (
                    <FilterButton
                        key={filter.id}
                        active={contentFilter === filter.id}
                        onClick={() => setContentFilter(filter.id)}
                    >
                        {filter.label}
                    </FilterButton>
                ))}
            </FilterGroup>
            <FilterGroup label="Period">
                {PERIOD_FILTERS.map((filter) => (
                    <FilterButton
                        key={filter.id}
                        active={periodFilter === filter.id}
                        onClick={() => setPeriodFilter(filter.id)}
                    >
                        {filter.label}
                    </FilterButton>
                ))}
            </FilterGroup>
        </div>
    );
}


function FilterGroup({ label, children }) {
    return (
        <section className="activity-filter-group" aria-label={label}>
            <div className="activity-filter-label">{label}</div>
            <div className="activity-filter-options">{children}</div>
        </section>
    );
}


function FilterButton({ active, onClick, children }) {
    return (
        <button
            type="button"
            className={active ? "activity-filter active" : "activity-filter"}
            onClick={onClick}
        >
            {children}
        </button>
    );
}


function ActivityEventCard({ event }) {
    return (
        <article className="activity-event-card">
            <div className="activity-event-meta">
                <div>
                    <h2>{activityTitle(event)}</h2>
                    <time>{formatDate(event.created_at)}</time>
                </div>
            </div>

            {event.comment?.body_preview && (
                <div className="activity-comment-preview">{event.comment.body_preview}</div>
            )}

            {event.content && (
                <div className="activity-content-preview">
                    <FeedContentCard item={event.content} removeItem={() => {}} />
                </div>
            )}

            {!event.content && isContentEvent(event) && (
                <div className="activity-placeholder">Publication is unavailable</div>
            )}

            {event.target_user && (
                <ActivityUserCard user={event.target_user} />
            )}
        </article>
    );
}


function ActivityUserCard({ user }) {
    const avatarSrc = getAvatarUrl(user, "small");
    return (
        <Link className="activity-user-card" to={`/people/@${user.username}`}>
            <img
                src={avatarSrc}
                onError={(event) => { event.currentTarget.src = "/assets/profile.svg"; }}
                alt={`${user.username} profile photo`}
            />
            <div>
                <div className="activity-user-name">{user.username}</div>
                <div className="activity-user-subtitle">
                    {user.subscribers_count.toLocaleString()} subscriber{user.subscribers_count === 1 ? "" : "s"}
                </div>
            </div>
        </Link>
    );
}


function activityTitle(event) {
    const contentType = event.content_type || "publication";
    const label = contentType === "post" ? "publication" : contentType;
    const article = ["article"].includes(label) ? "an" : "a";
    if (event.action_type === "content_view") {
        return `You viewed ${article} ${label}`;
    }
    if (event.action_type === "content_like") {
        return `You liked ${article} ${label}`;
    }
    if (event.action_type === "content_dislike") {
        return `You disliked ${article} ${label}`;
    }
    if (event.action_type === "content_comment") {
        return "You commented";
    }
    if (event.action_type === "user_follow") {
        return "You followed an author";
    }
    if (event.action_type === "user_unfollow") {
        return "You unfollowed an author";
    }
    if (event.action_type === "content_reaction_removed") {
        return "You removed a reaction";
    }
    return "Activity";
}


function isContentEvent(event) {
    return event.action_type?.startsWith("content_");
}


function formatDate(value) {
    if (!value) {
        return "";
    }
    return new Intl.DateTimeFormat(undefined, {
        dateStyle: "medium",
        timeStyle: "short",
    }).format(new Date(value));
}


export default Activity;
