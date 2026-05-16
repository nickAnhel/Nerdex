import { useContext, useState } from "react";
import { NavLink, useLocation, useNavigate } from "react-router-dom";
import "./FeedSidebar.css";

import { StoreContext } from "../..";
import PostService from "../../service/PostService";

import GlobalSearchInput from "../global-search-input/GlobalSearchInput";
import PostModal from "../post-modal/PostModal";


function FeedSidebar() {
    const { store } = useContext(StoreContext);
    const navigate = useNavigate();
    const location = useLocation();

    const [isCreatePostModalActive, setIsCreatePostModalActive] = useState(false);
    const [searchQuery, setSearchQuery] = useState("");
    const activeTab = new URLSearchParams(location.search).get("tab") || "recommendations";

    const navItemClass = (tabId) => (
        `feed-sidebar-item${activeTab === tabId ? " active" : ""}`
    );

    return (
        <div id="feed-sidebar">
            <GlobalSearchInput
                value={searchQuery}
                onChange={setSearchQuery}
                onSubmit={(query) => navigate(`/search?q=${encodeURIComponent(query)}&type=all`)}
                placeholder="Search all content"
            />

            <div id="feed-page-selector">
                <NavLink
                    to="/feed?tab=recommendations&type=all&sort=relevance"
                    className={navItemClass("recommendations")}
                >
                    Recommendations
                </NavLink>

                {
                    store.isAuthenticated &&
                    <NavLink
                        to="/feed?tab=subscriptions&type=all&sort=newest"
                        className={navItemClass("subscriptions")}
                    >
                        Subscriptions
                    </NavLink>
                }
            </div>

            {
                store.isAuthenticated &&
                <>
                    <hr />

                    <button className="btn btn-primary btn-block" onClick={() => { setIsCreatePostModalActive(true); }}>
                        Create Post
                    </button>
                    <NavLink to="/articles/new" className="btn btn-secondary btn-block">
                        Write Article
                    </NavLink>
                </>
            }

            <PostModal
                active={isCreatePostModalActive}
                setActive={setIsCreatePostModalActive}
                savePostFunc={PostService.createPost}
                modalHeader={"Create new post"}
                buttonText={"Create"}
                navigateTo={(post) => `/people/@${post.user.username}`}
            />
        </div>
    );
}

export default FeedSidebar;
