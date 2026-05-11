import { useContext, useEffect, useState } from "react"
import { Link } from "react-router-dom";

import "./Message.css";

import { StoreContext } from "../..";
import { getAvatarUrl } from "../../utils/avatar";


function Message({ userId, username, content, createdAt, avatarUrl = null, status = "sent", onRetry }) {
    const { store } = useContext(StoreContext);

    const createdAtTimeLocal = createdAt
        ? new Date(createdAt).toLocaleTimeString().split(":").slice(0, 2).join(":")
        : "";
    const [userProfilePhotoSrc, setUserProfilePhotoSrc] = useState(
        avatarUrl || (username === "You" ? getAvatarUrl(store.user, "small") : "/assets/profile.svg")
    );

    useEffect(() => {
        setUserProfilePhotoSrc(
            avatarUrl || (username === "You" ? getAvatarUrl(store.user, "small") : "/assets/profile.svg")
        );
    }, [avatarUrl, store.user, username]);

    return (
        <>
            <div className={`${username === "You" ? "msg you" : "msg"} ${status !== "sent" ? `msg-${status}` : ""}`}>
                <Link to={`/people/@${username === "You" ? store.user.username : username}`}>
                    <img
                        src={userProfilePhotoSrc}
                        onError={() => { setUserProfilePhotoSrc("/assets/profile.svg") }}
                        alt={username}
                    />
                </Link>
                <div className="msg-info">
                    <div className="msg-label">
                        <div className="username">{username}</div>
                        <div>{status === "pending" ? "Sending" : createdAtTimeLocal}</div>
                    </div>
                    <div className="msg-text">{content}</div>
                    {
                        status === "failed" &&
                        <button className="msg-retry" type="button" onClick={onRetry}>Retry</button>
                    }
                </div>
            </div>
        </>
    )
}

export default Message
