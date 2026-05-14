import { useContext, useState, useEffect } from "react";
import { useNavigate, useParams } from "react-router-dom";

import "./UserDetails.css";

import { StoreContext } from "../..";

import UserService from "../../service/UserService";
import ContentService from "../../service/ContentService";
import ChatService from "../../service/ChatService";

import NotFound from "../../components/not-found/NotFound";
import Loader from "../../components/loader/Loader";
import ContentList from "../../components/content-list/ContentList";
import UserList from "../../components/user-list/UserList";
import FeedContentCard from "../../components/feed-content-card/FeedContentCard";
import PostGalleryViewer from "../../components/post-gallery-viewer/PostGalleryViewer";
import PostDetails from "../post-details/PostDetails";
import { getAvatarUrl } from "../../utils/avatar";


const PUBLICATION_FILTERS = [
    { label: "All", value: null },
    { label: "Posts", value: "post" },
    { label: "Articles", value: "article" },
    { label: "Videos", value: "video" },
    { label: "Moments", value: "moment" },
];

const PROFILE_FILTERS = ["all", "public", "private", "drafts"];


function UserDetails() {
    const { store } = useContext(StoreContext);
    const navigate = useNavigate();
    const params = useParams();

    const [tab, setTab] = useState("publications");
    const [publicationType, setPublicationType] = useState(null);
    const [profileFilter, setProfileFilter] = useState("all");
    const [galleryItems, setGalleryItems] = useState([]);
    const [galleryActiveIndex, setGalleryActiveIndex] = useState(null);

    const [user, setUser] = useState({});
    const [isLoadingUser, setIsLoadingUser] = useState(true);
    const [userNotFound, setUserNotFound] = useState(false);

    const [avatarSrc, setAvatarSrc] = useState("");
    const [isLoadingSubscribe, setIsLoadingSubscribe] = useState(false);
    const [isLoadingDirectChat, setIsLoadingDirectChat] = useState(false);
    const [isSubscribed, setIsSubscribed] = useState(false);
    const [subsCount, setSubsCount] = useState(0);

    const username = (params.username || "").slice(1);
    const isOwner = Boolean(store.user?.user_id && store.user.user_id === user.user_id);

    const galleryAttachments = galleryItems.map((item) => item.attachment).filter(Boolean);

    useEffect(() => {
        const fetchUserData = async () => {
            setIsLoadingUser(true);
            setUserNotFound(false);

            try {
                const res = await UserService.getUserByUsername(username);
                setUser(res.data);
                setIsSubscribed(Boolean(res.data.is_subscribed));
                setSubsCount(res.data.subscribers_count || 0);
                setAvatarSrc(getAvatarUrl(res.data, "medium"));
                setTab("publications");
                setPublicationType(null);
                setProfileFilter("all");
            } catch (_error) {
                setUserNotFound(true);
            } finally {
                setIsLoadingUser(false);
            }
        };

        if (username) {
            fetchUserData();
        }
    }, [username]);

    useEffect(() => {
        setGalleryItems([]);
        setGalleryActiveIndex(null);
    }, [user.user_id, profileFilter, tab]);

    const handleSubscribe = async () => {
        if (!user.user_id) {
            return;
        }

        setIsLoadingSubscribe(true);

        try {
            await UserService.subscribeToUser(user.user_id);
            setIsSubscribed(true);
            setSubsCount((prev) => prev + 1);
        } catch (error) {
            console.log(error);
        } finally {
            setIsLoadingSubscribe(false);
        }
    };

    const handleUnsubscribe = async () => {
        if (!user.user_id) {
            return;
        }

        setIsLoadingSubscribe(true);

        try {
            await UserService.unsubscribFromuser(user.user_id);
            setIsSubscribed(false);
            setSubsCount((prev) => Math.max(0, prev - 1));
        } catch (error) {
            console.log(error);
        } finally {
            setIsLoadingSubscribe(false);
        }
    };

    const handleStartDirectChat = async () => {
        if (!user.user_id) {
            return;
        }

        setIsLoadingDirectChat(true);

        try {
            const res = await ChatService.createChat({
                chat_type: "direct",
                member_id: user.user_id,
            });
            navigate(`/chats/@${res.data.chat_id}`);
        } catch (error) {
            console.log(error);
        } finally {
            setIsLoadingDirectChat(false);
        }
    };

    const openGalleryViewer = (galleryItem) => {
        const index = galleryItems.findIndex((item) => (
            item.content_id === galleryItem.content_id
            && item.asset_id === galleryItem.asset_id
            && item.position === galleryItem.position
        ));
        if (index < 0) {
            return;
        }
        setGalleryActiveIndex(index);
    };

    if (userNotFound) {
        return (
            <div id="user-details">
                <NotFound />
            </div>
        );
    }

    if (isLoadingUser) {
        return (
            <div id="user-details">
                <div className="user-details-loader"><Loader /></div>
            </div>
        );
    }

    return (
        <div id="user-details">
            <div className="user-card">
                <img
                    src={avatarSrc}
                    alt={`${user.username} profile`}
                    onError={() => setAvatarSrc("/assets/profile.svg")}
                />

                <div className="user-data">
                    <div className="display-name">{user.display_name || user.username}</div>
                    <div className="username">@{user.username}</div>
                    {user.bio ? <div className="bio">{user.bio}</div> : null}
                    <div className="subs">{subsCount} subscriber{subsCount === 1 ? "" : "s"}</div>
                </div>

                {Array.isArray(user.links) && user.links.length > 0 ? (
                    <div className="user-links">
                        {user.links.map((link, index) => (
                            <a
                                key={`profile-link-${index}`}
                                href={link.url}
                                target="_blank"
                                rel="noreferrer"
                                className="user-link-item"
                            >
                                {link.label}
                            </a>
                        ))}
                    </div>
                ) : (
                    <div className="user-links-empty">No links</div>
                )}

                {isOwner ? (
                    <button
                        className="btn btn-primary"
                        type="button"
                        onClick={() => navigate("/profile")}
                    >
                        Edit profile
                    </button>
                ) : (
                    <>
                        <button
                            className="btn btn-outline-primary message-user"
                            onClick={(e) => {
                                e.preventDefault();
                                handleStartDirectChat();
                            }}
                            disabled={!store.isAuthenticated || isLoadingDirectChat}
                        >
                            {isLoadingDirectChat ? <Loader /> : "Message"}
                        </button>

                        {isSubscribed ? (
                            <button
                                className="btn btn-outline-primary unsubscribe"
                                onClick={(e) => {
                                    e.preventDefault();
                                    handleUnsubscribe();
                                }}
                                disabled={!store.isAuthenticated || isLoadingSubscribe}
                            >
                                {isLoadingSubscribe ? <Loader /> : "Unsubscribe"}
                            </button>
                        ) : (
                            <button
                                className="btn btn-primary"
                                onClick={(e) => {
                                    e.preventDefault();
                                    handleSubscribe();
                                }}
                                disabled={!store.isAuthenticated || isLoadingSubscribe}
                            >
                                {isLoadingSubscribe ? <Loader /> : "Subscribe"}
                            </button>
                        )}
                    </>
                )}
            </div>

            <div className="user-info">
                <div className="tabs">
                    <div
                        className={tab === "publications" ? "tab active" : "tab"}
                        onClick={() => setTab("publications")}
                    >
                        Publications
                    </div>
                    <div
                        className={tab === "gallery" ? "tab active" : "tab"}
                        onClick={() => setTab("gallery")}
                    >
                        Gallery
                    </div>
                    <div
                        className={tab === "subscriptions" ? "tab active" : "tab"}
                        onClick={() => setTab("subscriptions")}
                    >
                        Subscriptions
                    </div>
                </div>

                {tab === "publications" && user.user_id ? (
                    <>
                        <div className="publications-toolbar">
                            <div className="publication-type-filters">
                                {PUBLICATION_FILTERS.map((filter) => (
                                    <button
                                        key={filter.label}
                                        type="button"
                                        className={publicationType === filter.value ? "post-filter-chip active" : "post-filter-chip"}
                                        onClick={() => setPublicationType(filter.value)}
                                    >
                                        {filter.label}
                                    </button>
                                ))}
                            </div>

                            {isOwner ? (
                                <div className="publication-scope-filters">
                                    {PROFILE_FILTERS.map((filter) => (
                                        <button
                                            key={filter}
                                            type="button"
                                            className={profileFilter === filter ? "post-filter-chip active" : "post-filter-chip"}
                                            onClick={() => setProfileFilter(filter)}
                                        >
                                            {filter.charAt(0).toUpperCase() + filter.slice(1)}
                                        </button>
                                    ))}
                                </div>
                            ) : null}
                        </div>

                        <ContentList
                            fetchItems={ContentService.getPublications}
                            filters={{
                                author_id: user.user_id,
                                content_type: publicationType || undefined,
                                profile_filter: isOwner ? profileFilter : "public",
                                order: "published_at",
                                desc: true,
                            }}
                            refresh={`${store.isRefreshPosts}-publications-${user.user_id}-${publicationType || "all"}-${profileFilter}`}
                            emptyText="No publications"
                            renderItem={({ item, removeItem, ref }) => (
                                <FeedContentCard
                                    key={item.content_id}
                                    item={item}
                                    removeItem={removeItem}
                                    forwardedRef={ref}
                                />
                            )}
                        />
                    </>
                ) : null}

                {tab === "gallery" && user.user_id ? (
                    <>
                        {isOwner ? (
                            <div className="publication-scope-filters">
                                {PROFILE_FILTERS.map((filter) => (
                                    <button
                                        key={`gallery-${filter}`}
                                        type="button"
                                        className={profileFilter === filter ? "post-filter-chip active" : "post-filter-chip"}
                                        onClick={() => setProfileFilter(filter)}
                                    >
                                        {filter.charAt(0).toUpperCase() + filter.slice(1)}
                                    </button>
                                ))}
                            </div>
                        ) : null}

                        <div className="gallery-grid-list">
                            <ContentList
                                fetchItems={ContentService.getGallery}
                                filters={{
                                    author_id: user.user_id,
                                    profile_filter: isOwner ? profileFilter : "public",
                                    order: "created_at",
                                    desc: true,
                                }}
                                refresh={`${store.isRefreshPosts}-gallery-${user.user_id}-${profileFilter}`}
                                emptyText="No gallery items"
                                onItemsChange={setGalleryItems}
                                renderItem={({ item, ref }) => (
                                    <button
                                        key={`${item.content_id}-${item.asset_id}-${item.position}`}
                                        ref={ref}
                                        type="button"
                                        className="gallery-item"
                                        onClick={() => openGalleryViewer(item)}
                                    >
                                        <div className="gallery-media-wrap">
                                            {item.attachment.file_kind === "video" ? (
                                                <video
                                                    src={item.attachment.stream_url || item.attachment.original_url || item.attachment.preview_url}
                                                    poster={item.attachment.poster_url || item.attachment.preview_url || undefined}
                                                    muted
                                                    playsInline
                                                    preload="metadata"
                                                />
                                            ) : (
                                                <img
                                                    src={item.attachment.preview_url || item.attachment.original_url || "/assets/profile.svg"}
                                                    alt={item.excerpt || "Gallery item"}
                                                    onError={(e) => { e.currentTarget.src = "/assets/profile.svg"; }}
                                                />
                                            )}
                                            {item.attachment.file_kind === "video" ? <span className="gallery-video-badge">Video</span> : null}
                                        </div>
                                        <div className="gallery-item-meta">{item.excerpt || "Open media"}</div>
                                    </button>
                                )}
                            />
                        </div>
                    </>
                ) : null}

                {tab === "subscriptions" && user.user_id ? (
                    <UserList
                        fetchUsers={UserService.getSubsctiptions}
                        filters={{ user_id: user.user_id }}
                        refresh={`${user.user_id}-subs`}
                    />
                ) : null}
            </div>

            <PostDetails />
            <PostGalleryViewer
                attachments={galleryAttachments}
                activeIndex={galleryActiveIndex}
                onClose={() => setGalleryActiveIndex(null)}
                onChange={setGalleryActiveIndex}
            />
        </div>
    );
}


export default UserDetails;
