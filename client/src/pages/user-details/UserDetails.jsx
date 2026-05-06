import { useContext, useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useParams } from "react-router-dom";
import "./UserDetails.css"

import { StoreContext } from "../..";

import UserService from "../../service/UserService";
import PostService from "../../service/PostService";
import ArticleService from "../../service/ArticleService";
import VideoService from "../../service/VideoService";

import NotFound from "../../components/not-found/NotFound";
import Loader from "../../components/loader/Loader";
import PostModal from "../../components/post-modal/PostModal";
import PostDetails from "../post-details/PostDetails";

import PostList from "../../components/post-list/PostList";
import ContentList from "../../components/content-list/ContentList";
import UserList from "../../components/user-list/UserList";
import ArticleCard from "../../components/article-card/ArticleCard";
import VideoCard from "../../components/video-card/VideoCard";
import { getAvatarUrl } from "../../utils/avatar";


function UserDetails() {
    const { store } = useContext(StoreContext);
    const ownerPostFilters = ["all", "public", "private", "drafts"];
    const ownerArticleFilters = ["all", "public", "private", "drafts"];
    const ownerVideoFilters = ["all", "public", "private", "drafts"];
    const navigate = useNavigate();

    const [tab, setTab] = useState("posts");
    const [postFilter, setPostFilter] = useState("all");
    const [articleFilter, setArticleFilter] = useState("all");
    const [videoFilter, setVideoFilter] = useState("all");
    const [isCreatePostModalActive, setIsCreatePostModalActive] = useState(false);

    const params = useParams();
    const username = params.username.slice(1);

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
                setUserProfilePhotoSrc(getAvatarUrl(res.data, "medium"));
                setUserProfilePhotoStyle({});
                setTab("posts");
                setPostFilter("all");
                setArticleFilter("all");
                setVideoFilter("all");

            } catch (e) {
                setUserNotFound(true);
                console.log(e);
            }
        }

        fetchUserData();
    }, [username]);

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

    const isOwner = store.user.user_id === user.user_id;

    return (
        <div id="user-details">
            <div className="user-card">
                <img
                    src={userProfilePhotoSrc}
                    style={userProfilePhotoStyle}
                    alt={`${user.username} profile`}
                    onError={() => {
                        setUserProfilePhotoSrc("/assets/profile.svg");
                        setUserProfilePhotoStyle({ padding: ".5rem", opacity: ".1", aspectRatio: "1/1", backgroundColor: "#0a0a0a", border: "5px solid #fff" });
                    }}
                />

                <div className="user-data">
                    <div className="username">{user.username}</div>
                    <div className="subs">{subsCount} subscriber{subsCount === 1 ? "" : "s"}</div>
                </div>

                {
                    store.user.user_id !== user.user_id && (
                        isSubscribed ?
                            <button
                                className="btn btn-outline-primary unsubscribe"
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
                                className="btn btn-primary"
                                onClick={(e) => {
                                    e.preventDefault();
                                    handleSubscribe();
                                }}
                                disabled={!store.isAuthenticated || store.user.user_id === user.user_id}
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
                        className={tab === "articles" ? "tab active" : "tab"}
                        onClick={() => setTab("articles")}
                    >
                        Articles
                    </div>
                    <div
                        className={tab === "videos" ? "tab active" : "tab"}
                        onClick={() => setTab("videos")}
                    >
                        Videos
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
                    <>
                        {
                            isOwner &&
                            <div className="posts-toolbar">
                                <div className="post-filter-tabs">
                                    {ownerPostFilters.map((filter) => (
                                        <button
                                            key={filter}
                                            type="button"
                                            className={postFilter === filter ? "post-filter-chip active" : "post-filter-chip"}
                                            onClick={() => setPostFilter(filter)}
                                        >
                                            {filter.charAt(0).toUpperCase() + filter.slice(1)}
                                        </button>
                                    ))}
                                </div>

                                <button
                                    type="button"
                                    className="create-post-button btn btn-primary"
                                    onClick={() => setIsCreatePostModalActive(true)}
                                >
                                    Create post
                                </button>
                            </div>
                        }

                        {
                            user.user_id &&
                            <PostList
                                fetchPosts={PostService.getPosts}
                                filters={{
                                    desc: true,
                                    order: "created_at",
                                    user_id: user.user_id,
                                    profile_filter: isOwner ? postFilter : "public",
                                }}
                                refresh={`${store.isRefreshPosts}-${user.user_id}-${postFilter}`}
                            />
                        }
                    </>
                }

                {
                    tab === "articles" &&
                    <>
                        {
                            isOwner &&
                            <div className="posts-toolbar">
                                <div className="post-filter-tabs">
                                    {ownerArticleFilters.map((filter) => (
                                        <button
                                            key={filter}
                                            type="button"
                                            className={articleFilter === filter ? "post-filter-chip active" : "post-filter-chip"}
                                            onClick={() => setArticleFilter(filter)}
                                        >
                                            {filter.charAt(0).toUpperCase() + filter.slice(1)}
                                        </button>
                                    ))}
                                </div>

                                <button
                                    type="button"
                                    className="create-post-button btn btn-primary"
                                    onClick={() => navigate("/articles/new")}
                                >
                                    Write article
                                </button>
                            </div>
                        }

                        {
                            user.user_id &&
                            <ContentList
                                fetchItems={ArticleService.getArticles}
                                filters={{
                                    desc: true,
                                    order: "published_at",
                                    user_id: user.user_id,
                                    profile_filter: isOwner ? articleFilter : "public",
                                }}
                                refresh={`${store.isRefreshPosts}-articles-${user.user_id}-${articleFilter}`}
                                emptyText="No articles"
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
                        }
                    </>
                }

                {
                    tab === "videos" &&
                    <>
                        {
                            isOwner &&
                            <div className="posts-toolbar">
                                <div className="post-filter-tabs">
                                    {ownerVideoFilters.map((filter) => (
                                        <button
                                            key={filter}
                                            type="button"
                                            className={videoFilter === filter ? "post-filter-chip active" : "post-filter-chip"}
                                            onClick={() => setVideoFilter(filter)}
                                        >
                                            {filter.charAt(0).toUpperCase() + filter.slice(1)}
                                        </button>
                                    ))}
                                </div>

                                <button
                                    type="button"
                                    className="create-post-button btn btn-primary"
                                    onClick={() => navigate("/videos/new")}
                                >
                                    New video
                                </button>
                            </div>
                        }

                        {
                            user.user_id &&
                            <div className="profile-videos-list">
                                <ContentList
                                    fetchItems={VideoService.getVideos}
                                    filters={{
                                        desc: true,
                                        order: "published_at",
                                        user_id: user.user_id,
                                        profile_filter: isOwner ? videoFilter : "public",
                                    }}
                                    refresh={`${store.isRefreshPosts}-videos-${user.user_id}-${videoFilter}`}
                                    emptyText="No videos"
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
                        }
                    </>
                }

                {
                    tab === "subscriptions" &&
                    <UserList fetchUsers={UserService.getSubsctiptions} filters={{ user_id: user.user_id }} />
                }
            </div>

            <PostModal
                active={isCreatePostModalActive}
                setActive={setIsCreatePostModalActive}
                savePostFunc={PostService.createPost}
                modalHeader={"Create new post"}
                buttonText={"Create"}
                navigateTo={(post) => `/people/@${post.user.username}`}
            />
            <PostDetails />
        </div>
    )
}

export default UserDetails;
