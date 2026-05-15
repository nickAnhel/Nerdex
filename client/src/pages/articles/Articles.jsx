import { useContext, useState } from "react";
import { useNavigate } from "react-router-dom";

import "./Articles.css";

import { StoreContext } from "../..";
import ArticleService from "../../service/ArticleService";

import ContentList from "../../components/content-list/ContentList";
import ArticleCard from "../../components/article-card/ArticleCard";
import GlobalSearchInput from "../../components/global-search-input/GlobalSearchInput";


function Articles() {
    const { store } = useContext(StoreContext);
    const navigate = useNavigate();
    const [searchQuery, setSearchQuery] = useState("");

    return (
        <div id="articles-page">
            <div className="articles-page-header">
                <div>
                    <span className="articles-page-kicker">Long-form publishing</span>
                    <h1>Articles</h1>
                    <p>Editorial-style writing, deep dives, diagrams, code blocks, and threaded discussion.</p>
                </div>
                {
                    store.isAuthenticated &&
                    <button
                        type="button"
                        className="btn btn-primary"
                        onClick={() => navigate("/articles/new")}
                    >
                        Write article
                    </button>
                }
            </div>

            <GlobalSearchInput
                value={searchQuery}
                onChange={setSearchQuery}
                onSubmit={(query) => navigate(`/search?q=${encodeURIComponent(query)}&type=article`)}
                placeholder="Search articles and creators"
            />

            <ContentList
                fetchItems={ArticleService.getArticles}
                filters={{ desc: true, order: "published_at" }}
                refresh={store.isRefreshPosts}
                emptyText="No articles yet"
                renderItem={({ item, removeItem, ref }) => (
                    <ArticleCard
                        key={item.article_id || item.content_id}
                        ref={ref}
                        article={{
                            ...item,
                            article_id: item.article_id || item.content_id,
                        }}
                        removeItem={removeItem}
                    />
                )}
            />
        </div>
    );
}

export default Articles;
