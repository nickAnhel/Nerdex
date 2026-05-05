import { useContext } from "react";
import { Link } from "react-router-dom";

import "./Videos.css";

import { StoreContext } from "../..";
import ContentList from "../../components/content-list/ContentList";
import VideoCard from "../../components/video-card/VideoCard";
import VideoService from "../../service/VideoService";


function Videos() {
    const { store } = useContext(StoreContext);

    return (
        <main className="videos-page">
            <header className="videos-page-header">
                <div>
                    <h1>Videos</h1>
                    <p>Published videos from the Nerdex community.</p>
                </div>
                {
                    store.isAuthenticated &&
                    <Link to="/videos/new" className="videos-new-link">New video</Link>
                }
            </header>

            <ContentList
                fetchItems={(params) => VideoService.getVideos(params)}
                filters={{ order: "published_at", desc: true }}
                refresh={store.isRefreshPosts}
                emptyText="No videos yet"
                renderItem={({ item, removeItem, ref }) => (
                    <VideoCard
                        key={item.video_id || item.content_id}
                        ref={ref}
                        video={item}
                        removeItem={removeItem}
                    />
                )}
            />
        </main>
    );
}

export default Videos;
