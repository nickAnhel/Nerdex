import { useCallback, useContext, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import "./People.css";

import { StoreContext } from "../..";
import ContentService from "../../service/ContentService";
import UserService from "../../service/UserService";
import GlobalSearchInput from "../../components/global-search-input/GlobalSearchInput";
import Loader from "../../components/loader/Loader";
import PeopleAuthorCard from "./PeopleAuthorCard";


function People() {
    const RECOMMENDED_AUTHORS_LIMIT = 6;
    const { store } = useContext(StoreContext);
    const navigate = useNavigate();
    const [searchQuery, setSearchQuery] = useState("");
    const [subscriptions, setSubscriptions] = useState([]);
    const [recommendedAuthors, setRecommendedAuthors] = useState([]);

    const [isSubscriptionsLoading, setIsSubscriptionsLoading] = useState(false);
    const [isRecommendationsLoading, setIsRecommendationsLoading] = useState(false);
    const [subscriptionsError, setSubscriptionsError] = useState("");
    const [recommendationsError, setRecommendationsError] = useState("");

    const viewerId = store.user?.user_id || null;
    const isAuthenticated = Boolean(store.isAuthenticated && viewerId);

    const fetchSubscriptions = useCallback(async () => {
        if (!isAuthenticated || !viewerId) {
            setSubscriptions([]);
            setSubscriptionsError("");
            return;
        }
        setIsSubscriptionsLoading(true);
        setSubscriptionsError("");
        try {
            const response = await UserService.getSubscriptions({
                user_id: viewerId,
                offset: 0,
                limit: 50,
            });
            const items = Array.isArray(response.data) ? response.data : [];
            setSubscriptions(items.filter((item) => item.user_id !== viewerId));
        } catch (error) {
            setSubscriptionsError(error?.response?.data?.detail || "Failed to load subscriptions.");
            setSubscriptions([]);
        } finally {
            setIsSubscriptionsLoading(false);
        }
    }, [isAuthenticated, viewerId]);

    const fetchRecommendedAuthors = useCallback(async () => {
        if (!isAuthenticated || !viewerId) {
            setRecommendedAuthors([]);
            setRecommendationsError("");
            return;
        }
        setIsRecommendationsLoading(true);
        setRecommendationsError("");
        try {
            const response = await ContentService.getRecommendedAuthors({
                offset: 0,
                limit: RECOMMENDED_AUTHORS_LIMIT,
            });
            const items = Array.isArray(response.data) ? response.data : [];
            setRecommendedAuthors(
                items
                    .map((item) => item.author)
                    .filter((author) => author && author.user_id !== viewerId && !author.is_subscribed)
                    .slice(0, RECOMMENDED_AUTHORS_LIMIT)
            );
        } catch (error) {
            setRecommendationsError(error?.response?.data?.detail || "Failed to load recommendations.");
            setRecommendedAuthors([]);
        } finally {
            setIsRecommendationsLoading(false);
        }
    }, [isAuthenticated, viewerId]);

    useEffect(() => {
        fetchSubscriptions();
        fetchRecommendedAuthors();
    }, [fetchSubscriptions, fetchRecommendedAuthors]);

    const onFollowAuthor = useCallback((updatedUser) => {
        setRecommendedAuthors((prev) => prev.filter((user) => user.user_id !== updatedUser.user_id));
        setSubscriptions((prev) => {
            const existing = prev.find((user) => user.user_id === updatedUser.user_id);
            if (existing) {
                return prev.map((user) => (user.user_id === updatedUser.user_id ? updatedUser : user));
            }
            return [updatedUser, ...prev];
        });
    }, []);

    const onUnfollowAuthor = useCallback((updatedUser) => {
        setSubscriptions((prev) => prev.filter((user) => user.user_id !== updatedUser.user_id));
        setRecommendedAuthors((prev) => prev.map((user) => (
            user.user_id === updatedUser.user_id
                ? { ...user, is_subscribed: false, subscribers_count: updatedUser.subscribers_count }
                : user
        )));
    }, []);

    return (
        <div id="people">
            <GlobalSearchInput
                value={searchQuery}
                onChange={setSearchQuery}
                onSubmit={(query) => navigate(`/search?q=${encodeURIComponent(query)}&type=author`)}
                placeholder="Search creators"
            />
            <section className="people-columns">
                <section className="people-column">
                    <div className="people-column-header">
                        <h2>Subscriptions</h2>
                    </div>
                    {
                        !isAuthenticated &&
                        <div className="people-column-state">Sign in to view your subscriptions.</div>
                    }
                    {
                        isAuthenticated && isSubscriptionsLoading &&
                        <div className="people-column-loader"><Loader /></div>
                    }
                    {
                        isAuthenticated && !isSubscriptionsLoading && subscriptionsError &&
                        <div className="people-column-state error">{subscriptionsError}</div>
                    }
                    {
                        isAuthenticated && !isSubscriptionsLoading && !subscriptionsError && subscriptions.length === 0 &&
                        <div className="people-column-state">You are not subscribed to any authors yet.</div>
                    }
                    {
                        isAuthenticated && !isSubscriptionsLoading && !subscriptionsError && subscriptions.length > 0 &&
                        <div className="people-author-list">
                            {
                                subscriptions.map((user) => (
                                    <PeopleAuthorCard
                                        key={`subscription-${user.user_id}`}
                                        user={user}
                                        actionType="unfollow"
                                        isAuthenticated={isAuthenticated}
                                        viewerId={viewerId}
                                        onActionSuccess={onUnfollowAuthor}
                                    />
                                ))
                            }
                        </div>
                    }
                </section>
                <section className="people-column">
                    <div className="people-column-header">
                        <h2>Recommended authors</h2>
                    </div>
                    {
                        !isAuthenticated &&
                        <div className="people-column-state">Sign in to get personalized recommendations.</div>
                    }
                    {
                        isAuthenticated && isRecommendationsLoading &&
                        <div className="people-column-loader"><Loader /></div>
                    }
                    {
                        isAuthenticated && !isRecommendationsLoading && recommendationsError &&
                        <div className="people-column-state error">{recommendationsError}</div>
                    }
                    {
                        isAuthenticated && !isRecommendationsLoading && !recommendationsError && recommendedAuthors.length === 0 &&
                        <div className="people-column-state">No recommended authors yet.</div>
                    }
                    {
                        isAuthenticated && !isRecommendationsLoading && !recommendationsError && recommendedAuthors.length > 0 &&
                        <div className="people-author-list">
                            {
                                recommendedAuthors.map((user) => (
                                    <PeopleAuthorCard
                                        key={`recommendation-${user.user_id}`}
                                        user={user}
                                        actionType="follow"
                                        isAuthenticated={isAuthenticated}
                                        viewerId={viewerId}
                                        onActionSuccess={onFollowAuthor}
                                    />
                                ))
                            }
                        </div>
                    }
                </section>
            </section>
        </div>
    );
}

export default People;
