import { useContext } from "react";
import "./GlobalFeed.css";

import { StoreContext } from "../..";
import ContentService from "../../service/ContentService";

import ContentList from "../../components/content-list/ContentList";
import FeedContentCard from "../../components/feed-content-card/FeedContentCard";


function GlobalFeed() {
    const { store } = useContext(StoreContext);

    return (
        <div id="global-feed">
            <ContentList
                fetchItems={ContentService.getFeed}
                filters={{ desc: true, order: "created_at" }}
                refresh={store.isRefreshPosts}
                emptyText="No content"
                renderItem={({ item, removeItem, ref }) => (
                    <FeedContentCard
                        key={item.content_id}
                        item={item}
                        removeItem={removeItem}
                        forwardedRef={ref}
                    />
                )}
            />
        </div>
    )
}

export default GlobalFeed;
