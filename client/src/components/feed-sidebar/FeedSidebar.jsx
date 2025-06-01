import { useContext, useState } from "react";
import { NavLink } from "react-router-dom"
import "./FeedSidebar.css";

import { StoreContext } from "../..";
import PostService from "../../service/PostService";

import PostModal from "../post-modal/PostModal";


function FeedSidebar() {
    const { store } = useContext(StoreContext);

    const [isCreatePostModalActive, setIsCreatePostModalActive] = useState(false);

    return (
        <div id="feed-sidebar">
            <div id="feed-page-selector">
                <NavLink end to="/feed" className="feed-sidebar-item" >
                    Global
                </NavLink>

                {
                    store.isAuthenticated &&
                    <NavLink to="/feed/personal" className="feed-sidebar-item">
                        Personal
                    </NavLink>
                }
            </div>

            {
                store.isAuthenticated &&
                <>
                    <hr />

                    <button onClick={() => { setIsCreatePostModalActive(true); }}>
                        Create Post
                    </button>
                </>
            }

            <PostModal
                active={isCreatePostModalActive}
                setActive={setIsCreatePostModalActive}
                savePostFunc={PostService.createPost}
                modalHeader={"Create new post"}
                buttonText={"Create"}
                navigateTo={`/people/@${store.user.username}`}
            />
        </div>
    );
}

export default FeedSidebar;