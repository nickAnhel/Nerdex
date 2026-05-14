import { useContext, useEffect } from "react";
import { Link, useSearchParams } from "react-router-dom";

import "./Videos.css";

import { StoreContext } from "../..";
import ContentList from "../../components/content-list/ContentList";
import VideoCard from "../../components/video-card/VideoCard";
import ContentService from "../../service/ContentService";
import VideoService from "../../service/VideoService";


const VIDEO_TABS = {
    recommendations: "recommendations",
    subscriptions: "subscriptions",
};

const VIDEO_SECTIONS = [
    {
        id: VIDEO_TABS.recommendations,
        label: "Recommendations",
        description: "Public videos ranked by current activity.",
        icon: <RecommendationsIcon />,
    },
    {
        id: VIDEO_TABS.subscriptions,
        label: "Subscriptions",
        description: "Ready videos from people you follow.",
        authOnly: true,
        icon: <SubscriptionsIcon />,
    },
];

function withoutInternalFilters(params) {
    const nextParams = { ...params };
    delete nextParams.section;
    return nextParams;
}


function Videos() {
    const { store } = useContext(StoreContext);
    const [searchParams, setSearchParams] = useSearchParams();
    const requestedTab = searchParams.get("tab") || VIDEO_TABS.recommendations;

    const tabs = VIDEO_SECTIONS.filter((tab) => !tab.authOnly || store.isAuthenticated);
    const activeTab = tabs.some((tab) => tab.id === requestedTab)
        ? requestedTab
        : VIDEO_TABS.recommendations;
    const activeSection = tabs.find((tab) => tab.id === activeTab) || tabs[0];

    useEffect(() => {
        if (requestedTab !== activeTab) {
            setSearchParams({ tab: activeTab }, { replace: true });
        }
    }, [activeTab, requestedTab, setSearchParams]);

    const setActiveTab = (tabId) => {
        setSearchParams({ tab: tabId });
    };

    const renderTabContent = () => {
        const fetchItems = activeTab === VIDEO_TABS.subscriptions
            ? ContentService.getVideoSubscriptions
            : activeTab === VIDEO_TABS.recommendations
                ? ContentService.getVideoRecommendations
                : VideoService.getVideos;

        return (
            <div className="videos-grid-panel">
                <ContentList
                    key={activeTab}
                    fetchItems={(params) => fetchItems(withoutInternalFilters(params))}
                    filters={{ order: "published_at", desc: true, section: activeTab }}
                    refresh={`${store.isRefreshPosts}-${activeTab}`}
                    emptyText="No videos yet"
                    renderItem={({ item, removeItem, ref }) => (
                        <VideoCard
                            key={item.video_id || item.content_id}
                            ref={ref}
                            video={{
                                ...item,
                                video_id: item.video_id || item.content_id,
                            }}
                            removeItem={removeItem}
                        />
                    )}
                />
            </div>
        );
    };

    return (
        <main className="videos-page">
            <aside className="videos-sidebar" aria-label="Video sections">
                <Link to="/videos?tab=recommendations" className="videos-brand">
                    <span className="videos-brand-icon"><PlayTileIcon /></span>
                    <span>Videos</span>
                </Link>
                <nav className="videos-nav">
                    {tabs.map((tab) => (
                        <button
                            key={tab.id}
                            type="button"
                            className={activeTab === tab.id ? "active" : ""}
                            onClick={() => setActiveTab(tab.id)}
                        >
                            {tab.icon}
                            <span>{tab.label}</span>
                        </button>
                    ))}
                </nav>
                {
                    store.isAuthenticated &&
                    <Link
                        to="/videos/new"
                        className="videos-new-link"
                    >
                        New video
                    </Link>
                }
            </aside>

            <section className="videos-content">
                <header className="videos-page-header">
                    <div>
                        <h1>{activeSection.label}</h1>
                        <p>{activeSection.description}</p>
                    </div>
                </header>

                {renderTabContent()}
            </section>
        </main>
    );
}

function VideoNavIcon({ children }) {
    return (
        <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
            {children}
        </svg>
    );
}

function RecommendationsIcon() {
    return (
        <VideoNavIcon>
            <path d="M4 5.5A2.5 2.5 0 0 1 6.5 3h11A2.5 2.5 0 0 1 20 5.5v13a2.5 2.5 0 0 1-2.5 2.5h-11A2.5 2.5 0 0 1 4 18.5v-13Zm5.5 3.1v6.8L15 12l-5.5-3.4Z" fill="currentColor" />
        </VideoNavIcon>
    );
}

function SubscriptionsIcon() {
    return (
        <VideoNavIcon>
            <path d="M7 4h10a3 3 0 0 1 3 3v8a3 3 0 0 1-3 3H9l-4 3v-3a3 3 0 0 1-3-3V7a3 3 0 0 1 3-3h2Zm3 4v6l5-3-5-3Z" fill="currentColor" />
        </VideoNavIcon>
    );
}

function PlayTileIcon() {
    return (
        <VideoNavIcon>
            <path d="M3 7a4 4 0 0 1 4-4h10a4 4 0 0 1 4 4v10a4 4 0 0 1-4 4H7a4 4 0 0 1-4-4V7Zm7 1.8v6.4l5.2-3.2L10 8.8Z" fill="currentColor" />
        </VideoNavIcon>
    );
}

export default Videos;
