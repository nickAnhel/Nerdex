import { Outlet } from "react-router-dom";
import "./Feed.css";

import FeedSidebar from "../../components/feed-sidebar/FeedSidebar";


function Feed() {
    return (
        <div id="feed">
            <FeedSidebar />
            <Outlet />
        </div>
    )
}

export default Feed;