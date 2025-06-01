import "./PersonalFeed.css";

import PostService from "../../service/PostService";

import PostList from "../../components/post-list/PostList";


function PersonalFeed() {
    return (
        <div id="personal-feed">
            <PostList fetchPosts={PostService.getSubscriptionsPosts} filters={{ desc: true, order: "created_at" }}/>
        </div>
    )
}

export default PersonalFeed;