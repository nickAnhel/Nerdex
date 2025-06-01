import { useContext, useState, useEffect } from "react";
import { useParams } from "react-router-dom";
import "./UserDetails.css"

import { StoreContext } from "../..";

import UserService from "../../service/UserService";
import PostService from "../../service/PostService";

import NotFound from "../../components/not-found/NotFound";
import Loader from "../../components/loader/Loader";

import PostList from "../../components/post-list/PostList";
import UserList from "../../components/user-list/UserList";


function UserDetails() {
    const { store } = useContext(StoreContext);

    const [tab, setTab] = useState("posts");

    const params = useParams();
    const username = params.username.slice(1);

    const [postsElement, setPostsElement] = useState();

    const [user, setUser] = useState({});

    const [userProfilePhotoStyle, setUserProfilePhotoStyle] = useState({});
    const [userProfilePhotoSrc, setUserProfilePhotoSrc] = useState("");

    const [userNotFound, setUserNotFound] = useState(false);

    const [isLoadingSubscribe, setIsLoadingSubscribe] = useState(false);
    const [isSubscribed, setIsSubsctribed] = useState(false);
    const [subsCount, setSubsCount] = useState(0);

    useEffect(() => {
        const fetchUserData = async () => {
            try {
                const res = await UserService.getUserByUsername(username);
                setUser(res.data);
                setIsSubsctribed(res.data.is_subscribed);
                setSubsCount(res.data.subscribers_count);
                setUserProfilePhotoSrc(`${process.env.REACT_APP_STORAGE_URL}PPl@${res.data.user_id}?${performance.now()}`);
                setUserProfilePhotoStyle({});
                setTab("posts");

                setPostsElement(
                    <PostList fetchPosts={PostService.getPosts} filters={{ desc: true, order: "created_at", user_id: res.data.user_id }} refresh={user} />
                );

            } catch (e) {
                setUserNotFound(true);
                console.log(e);
            }
        }

        fetchUserData();
    }, [params.username]);

    const handleSubscribe = async () => {
        setIsLoadingSubscribe(true);

        try {
            await UserService.subscribeToUser(user.user_id);
            setIsSubsctribed(true);
            setSubsCount((prev) => prev + 1);

        } catch (e) {
            console.log(e);
            // alertsContext.addAlert({
            //     text: "Failed to subscribe to channel",
            //     time: 2000,
            //     type: "error"
            // })
            return;
        }

        setIsLoadingSubscribe(false);
        // alertsContext.addAlert({
        //     text: "Successfully subscribed to channel",
        //     time: 2000,
        //     type: "success"
        // })
    }

    const handleUnsubscribe = async () => {
        setIsLoadingSubscribe(true);

        try {
            await UserService.unsubscribFromuser(user.user_id);
            setIsSubsctribed(false);
            setSubsCount((prev) => prev - 1);

        } catch (e) {
            // alertsContext.addAlert({
            //     text: "Failed to unsubscribe from channel",
            //     time: 2000,
            //     type: "error"
            // })
            console.log(e);
        }

        setIsLoadingSubscribe(false);
        // alertsContext.addAlert({
        //     text: "Successfully unsubscribed from channel",
        //     time: 2000,
        //     type: "success"
        // })
    }

    if (userNotFound) {
        return (
            <div id="user-details">
                <NotFound />
            </div>
        )
    }

    return (
        <div id="user-details">
            <div className="user-card">
                <img
                    src={userProfilePhotoSrc}
                    style={userProfilePhotoStyle}
                    alt={`${user.username} profile photo`}
                    onError={() => {
                        setUserProfilePhotoSrc("../../../assets/profile.svg");
                        setUserProfilePhotoStyle({ padding: ".5rem", opacity: ".1", aspectRatio: "1/1", backgroundColor: "#0a0a0a", border: "5px solid #fff" });
                    }}
                />

                <div className="user-data">
                    <div className="username">{user.username}</div>
                    <div className="subs">{subsCount} subscriber{subsCount == 1 ? "" : "s"}</div>
                </div>

                {
                    store.user.user_id != user.user_id && (
                        isSubscribed ?
                            <button
                                className="btn unsubscribe"
                                onClick={(e) => {
                                    e.preventDefault();
                                    handleUnsubscribe();
                                }}
                                disabled={!store.isAuthenticated}
                            >
                                {isLoadingSubscribe ? <Loader /> : "Unsubscribe"}
                            </button>
                            :
                            <button
                                className="btn"
                                onClick={(e) => {
                                    e.preventDefault();
                                    handleSubscribe();
                                }}
                                disabled={!store.isAuthenticated || store.user.user_id == user.user_id}
                            >
                                {isLoadingSubscribe ? <Loader /> : "Subscribe"}
                            </button>
                    )
                }
            </div>

            <div className="user-info">
                <div className="tabs">
                    <div
                        className={tab === "posts" ? "tab active" : "tab"}
                        onClick={() => setTab("posts")}
                    >
                        Posts
                    </div>
                    <div
                        className={tab === "subscriptions" ? "tab active" : "tab"}
                        onClick={() => setTab("subscriptions")}
                    >
                        Subscriptions
                    </div>
                </div>

                {
                    tab === "posts" &&
                    postsElement
                }

                {
                    tab === "subscriptions" &&
                    <UserList fetchUsers={UserService.getSubsctiptions} filters={{ user_id: user.user_id }} />
                }
            </div>
        </div>
    )
}

export default UserDetails;