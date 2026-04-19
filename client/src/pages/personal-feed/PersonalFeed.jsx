import { useContext } from "react";
import "./PersonalFeed.css";

import { StoreContext } from "../..";
import ContentService from "../../service/ContentService";

import ContentList from "../../components/content-list/ContentList";
import FeedContentCard from "../../components/feed-content-card/FeedContentCard";


function PersonalFeed() {
    const { store } = useContext(StoreContext);

    return (
        <div id="personal-feed">
            <ContentList
                fetchItems={ContentService.getSubscriptionsFeed}
                filters={{ desc: true, order: "created_at" }}
                refresh={store.isRefreshPosts}
                emptyText="No content from subscriptions"
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

export default PersonalFeed;
