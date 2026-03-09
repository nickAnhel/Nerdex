import { useContext } from "react";
import "./PersonalFeed.css";

import { StoreContext } from "../..";
import PostService from "../../service/PostService";

import PostList from "../../components/post-list/PostList";


function PersonalFeed() {
    const { store } = useContext(StoreContext);

    return (
        <div id="personal-feed">
            <PostList
                fetchPosts={PostService.getSubscriptionsPosts}
                filters={{ desc: true, order: "created_at" }}
                refresh={store.isRefreshPosts}
            />
        </div>
    )
}

export default PersonalFeed;
