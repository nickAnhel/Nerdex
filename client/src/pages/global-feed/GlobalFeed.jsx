import { useContext } from "react";
import "./GlobalFeed.css";

import { StoreContext } from "../..";
import PostService from "../../service/PostService";

import PostList from "../../components/post-list/PostList";


function GlobalFeed() {
    const { store } = useContext(StoreContext);

    return (
        <div id="global-feed">
            <PostList fetchPosts={PostService.getPosts} filters={{ desc: true, order: "created_at" }} refresh={store.isRefreshPosts}/>
        </div>
    )
}

export default GlobalFeed;