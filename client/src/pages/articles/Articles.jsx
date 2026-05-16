import { useContext, useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import "./Articles.css";

import { StoreContext } from "../..";
import ContentService from "../../service/ContentService";

import ContentList from "../../components/content-list/ContentList";
import ArticleCard from "../../components/article-card/ArticleCard";
import GlobalSearchInput from "../../components/global-search-input/GlobalSearchInput";

const ARTICLE_TABS = {
    recommendations: "recommendations",
    subscriptions: "subscriptions",
};


function Articles() {
    const { store } = useContext(StoreContext);
    const navigate = useNavigate();
    const [searchParams, setSearchParams] = useSearchParams();
    const [searchQuery, setSearchQuery] = useState("");
    const requestedTab = searchParams.get("tab") || ARTICLE_TABS.recommendations;
    const activeTab = (
        requestedTab === ARTICLE_TABS.subscriptions && store.isAuthenticated
            ? ARTICLE_TABS.subscriptions
            : ARTICLE_TABS.recommendations
    );

    useEffect(() => {
        if (requestedTab !== activeTab) {
            setSearchParams({ tab: activeTab }, { replace: true });
        }
    }, [activeTab, requestedTab, setSearchParams]);

    const setTab = (tab) => {
        setSearchParams({ tab });
    };

    const fetchItems = activeTab === ARTICLE_TABS.subscriptions
        ? ContentService.getSubscriptionsFeed
        : ContentService.getRecommendationsFeed;
    const filters = activeTab === ARTICLE_TABS.subscriptions
        ? {
            content_type: "article",
            order: "published_at",
            desc: true,
        }
        : {
            content_type: "article",
            sort: "relevance",
        };
    const emptyText = activeTab === ARTICLE_TABS.subscriptions
        ? "No articles from subscriptions"
        : "No article recommendations yet";

    return (
        <div id="articles-page">
            <div className="articles-page-header">
                <div>
                    <span className="articles-page-kicker">Long-form publishing</span>
                    <h1>Articles</h1>
                    <p>Editorial-style writing, deep dives, diagrams, code blocks, and threaded discussion.</p>
                </div>
                {
                    store.isAuthenticated &&
                    <button
                        type="button"
                        className="btn btn-primary"
                        onClick={() => navigate("/articles/new")}
                    >
                        Write article
                    </button>
                }
            </div>

            <GlobalSearchInput
                value={searchQuery}
                onChange={setSearchQuery}
                onSubmit={(query) => navigate(`/search?q=${encodeURIComponent(query)}&type=article`)}
                placeholder="Search articles and creators"
            />

            <div className="articles-page-sections" role="tablist" aria-label="Article sections">
                <button
                    type="button"
                    className={activeTab === ARTICLE_TABS.recommendations ? "active" : ""}
                    onClick={() => setTab(ARTICLE_TABS.recommendations)}
                >
                    Recommendations
                </button>
                {
                    store.isAuthenticated &&
                    <button
                        type="button"
                        className={activeTab === ARTICLE_TABS.subscriptions ? "active" : ""}
                        onClick={() => setTab(ARTICLE_TABS.subscriptions)}
                    >
                        Subscriptions
                    </button>
                }
            </div>

            <ContentList
                key={`articles-${activeTab}`}
                fetchItems={fetchItems}
                filters={filters}
                refresh={`${store.isRefreshPosts}-${activeTab}`}
                emptyText={emptyText}
                renderItem={({ item, removeItem, ref }) => (
                    <ArticleCard
                        key={item.article_id || item.content_id}
                        ref={ref}
                        article={{
                            ...item,
                            article_id: item.article_id || item.content_id,
                        }}
                        removeItem={removeItem}
                    />
                )}
            />
        </div>
    );
}

export default Articles;
