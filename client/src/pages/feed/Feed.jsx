import { Outlet } from "react-router-dom";
import "./Feed.css";

import FeedSidebar from "../../components/feed-sidebar/FeedSidebar";
import PostDetails from "../post-details/PostDetails";


function Feed() {
    return (
        <div id="feed">
            <FeedSidebar />
            <Outlet />
            <PostDetails />
        </div>
    )
}

export default Feed;
