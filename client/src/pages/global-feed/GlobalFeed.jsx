import { useContext, useEffect, useMemo } from "react";
import { useSearchParams } from "react-router-dom";

import "./GlobalFeed.css";

import { StoreContext } from "../..";
import ContentService from "../../service/ContentService";

import ContentList from "../../components/content-list/ContentList";
import FeedContentCard from "../../components/feed-content-card/FeedContentCard";


const FEED_TABS = {
    recommendations: "recommendations",
    subscriptions: "subscriptions",
};

const CONTENT_TYPES = [
    { id: "all", label: "All" },
    { id: "post", label: "Posts" },
    { id: "video", label: "Videos" },
    { id: "article", label: "Articles" },
    { id: "moment", label: "Moments" },
];

const RECOMMENDATION_SORTS = [
    { id: "relevance", label: "Relevance" },
    { id: "newest", label: "Newest" },
    { id: "oldest", label: "Oldest" },
];

const SUBSCRIPTION_SORTS = [
    { id: "newest", label: "Newest" },
    { id: "oldest", label: "Oldest" },
];

function normalizeTab(tab, isAuthenticated) {
    if (tab === FEED_TABS.subscriptions) {
        return isAuthenticated ? tab : FEED_TABS.recommendations;
    }
    return tab === FEED_TABS.recommendations ? tab : FEED_TABS.recommendations;
}

function normalizeContentType(contentType) {
    return CONTENT_TYPES.some((item) => item.id === contentType) ? contentType : "all";
}

function normalizeSort(tab, sort) {
    const allowed = tab === FEED_TABS.subscriptions
        ? SUBSCRIPTION_SORTS
        : RECOMMENDATION_SORTS;
    const defaultSort = allowed[0].id;
    return allowed.some((item) => item.id === sort) ? sort : defaultSort;
}

function mapSubscriptionFilters(contentType, sort) {
    return {
        content_type: contentType === "all" ? undefined : contentType,
        order: "published_at",
        desc: sort !== "oldest",
    };
}

function GlobalFeed() {
    const { store } = useContext(StoreContext);
    const [searchParams, setSearchParams] = useSearchParams();

    const requestedTab = searchParams.get("tab") || FEED_TABS.recommendations;
    const requestedContentType = searchParams.get("type") || "all";
    const requestedSort = searchParams.get("sort") || "relevance";

    const activeTab = normalizeTab(requestedTab, store.isAuthenticated);
    const activeContentType = normalizeContentType(requestedContentType);
    const activeSort = normalizeSort(activeTab, requestedSort);

    useEffect(() => {
        if (
            requestedTab !== activeTab
            || requestedContentType !== activeContentType
            || requestedSort !== activeSort
        ) {
            setSearchParams({
                tab: activeTab,
                type: activeContentType,
                sort: activeSort,
            }, { replace: true });
        }
    }, [
        activeContentType,
        activeSort,
        activeTab,
        requestedContentType,
        requestedSort,
        requestedTab,
        setSearchParams,
    ]);

    const availableTabs = useMemo(() => (
        [
            { id: FEED_TABS.recommendations, label: "Recommendations" },
            ...(store.isAuthenticated ? [{ id: FEED_TABS.subscriptions, label: "Subscriptions" }] : []),
        ]
    ), [store.isAuthenticated]);

    const availableSorts = activeTab === FEED_TABS.subscriptions
        ? SUBSCRIPTION_SORTS
        : RECOMMENDATION_SORTS;

    const setTab = (tab) => {
        setSearchParams({
            tab,
            type: activeContentType,
            sort: normalizeSort(tab, activeSort),
        });
    };

    const setContentType = (contentType) => {
        setSearchParams({
            tab: activeTab,
            type: contentType,
            sort: activeSort,
        });
    };

    const setSort = (sort) => {
        setSearchParams({
            tab: activeTab,
            type: activeContentType,
            sort,
        });
    };

    const fetchItems = activeTab === FEED_TABS.subscriptions
        ? ContentService.getSubscriptionsFeed
        : ContentService.getRecommendationsFeed;
    const filters = activeTab === FEED_TABS.subscriptions
        ? mapSubscriptionFilters(activeContentType, activeSort)
        : {
            content_type: activeContentType,
            sort: activeSort,
        };

    return (
        <main id="global-feed">
            <header className="global-feed-header">
                <div className="global-feed-tabs" role="tablist" aria-label="Feed tabs">
                    {availableTabs.map((tab) => (
                        <button
                            key={tab.id}
                            type="button"
                            className={activeTab === tab.id ? "active" : ""}
                            onClick={() => setTab(tab.id)}
                        >
                            {tab.label}
                        </button>
                    ))}
                </div>

                <div className="global-feed-controls">
                    <div className="global-feed-types" role="tablist" aria-label="Content type filters">
                        {CONTENT_TYPES.map((type) => (
                            <button
                                key={type.id}
                                type="button"
                                className={activeContentType === type.id ? "active" : ""}
                                onClick={() => setContentType(type.id)}
                            >
                                {type.label}
                            </button>
                        ))}
                    </div>

                    <label className="global-feed-sort" htmlFor="global-feed-sort-select">
                        Sort
                        <select
                            id="global-feed-sort-select"
                            value={activeSort}
                            onChange={(event) => setSort(event.target.value)}
                        >
                            {availableSorts.map((sort) => (
                                <option key={sort.id} value={sort.id}>
                                    {sort.label}
                                </option>
                            ))}
                        </select>
                    </label>
                </div>
            </header>

            <ContentList
                key={`${activeTab}-${activeContentType}-${activeSort}`}
                fetchItems={fetchItems}
                filters={filters}
                refresh={`${store.isRefreshPosts}-${activeTab}-${activeContentType}-${activeSort}`}
                emptyText={activeTab === FEED_TABS.subscriptions ? "No content from subscriptions" : "No recommendations yet"}
                renderItem={({ item, removeItem, ref }) => (
                    <FeedContentCard
                        key={item.content_id}
                        item={item}
                        removeItem={removeItem}
                        forwardedRef={ref}
                    />
                )}
            />
        </main>
    );
}

export default GlobalFeed;
