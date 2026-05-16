import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import UserService from "../../service/UserService";
import Loader from "../../components/loader/Loader";
import { getAvatarUrl } from "../../utils/avatar";


function PeopleAuthorCard({
    user,
    actionType,
    isAuthenticated,
    viewerId,
    onActionSuccess,
}) {
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState("");

    const canFollow = actionType === "follow"
        && isAuthenticated
        && viewerId
        && viewerId !== user.user_id;
    const canUnfollow = actionType === "unfollow" && isAuthenticated;
    const displayName = user.display_name || user.username;
    const bioPreview = useMemo(() => {
        if (!user.bio) {
            return "";
        }
        const normalized = user.bio.trim();
        if (normalized.length <= 120) {
            return normalized;
        }
        return `${normalized.slice(0, 117)}...`;
    }, [user.bio]);

    const handleAction = async (event) => {
        event.preventDefault();
        if (isLoading) {
            return;
        }
        setError("");
        setIsLoading(true);
        try {
            if (actionType === "follow") {
                await UserService.subscribeToUser(user.user_id);
                onActionSuccess?.({
                    ...user,
                    is_subscribed: true,
                    subscribers_count: (user.subscribers_count || 0) + 1,
                });
            } else if (actionType === "unfollow") {
                await UserService.unsubscribeFromUser(user.user_id);
                onActionSuccess?.({
                    ...user,
                    is_subscribed: false,
                    subscribers_count: Math.max(0, (user.subscribers_count || 0) - 1),
                });
            }
        } catch (requestError) {
            setError(requestError?.response?.data?.detail || "Action failed.");
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <Link className="people-author-card" to={`/people/@${user.username}`}>
            <div className="people-author-main">
                <img
                    className="people-author-avatar"
                    src={getAvatarUrl(user, "small")}
                    onError={(event) => { event.currentTarget.src = "/assets/profile.svg"; }}
                    alt={`${user.username} avatar`}
                />
                <div className="people-author-info">
                    <div className="people-author-display-name">{displayName}</div>
                    <div className="people-author-username">@{user.username}</div>
                    {bioPreview ? <div className="people-author-bio">{bioPreview}</div> : null}
                    <div className="people-author-subscribers">
                        {(user.subscribers_count || 0).toLocaleString()} subscriber{(user.subscribers_count || 0) === 1 ? "" : "s"}
                    </div>
                    {error ? <div className="people-author-error">{error}</div> : null}
                </div>
            </div>
            <div className="people-author-actions">
                {
                    actionType === "follow" &&
                    <button
                        type="button"
                        className="btn btn-primary"
                        disabled={!canFollow || isLoading}
                        onClick={handleAction}
                    >
                        {isLoading ? <Loader /> : "Follow"}
                    </button>
                }
                {
                    actionType === "unfollow" &&
                    <button
                        type="button"
                        className="btn btn-outline-primary unsubscribe"
                        disabled={!canUnfollow || isLoading}
                        onClick={handleAction}
                    >
                        {isLoading ? <Loader /> : "Unfollow"}
                    </button>
                }
            </div>
        </Link>
    );
}

export default PeopleAuthorCard;
