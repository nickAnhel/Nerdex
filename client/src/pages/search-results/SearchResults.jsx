import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useQuery } from "@siberiacancode/reactuse";

import "./SearchResults.css";

import GlobalSearchInput from "../../components/global-search-input/GlobalSearchInput";
import FeedContentCard from "../../components/feed-content-card/FeedContentCard";
import Loader from "../../components/loader/Loader";
import UserListItem from "../../components/user-list-item/UserListItem";
import SearchService from "../../service/SearchService";


const SEARCH_TYPES = [
    { value: "all", label: "All" },
    { value: "post", label: "Posts" },
    { value: "video", label: "Videos" },
    { value: "article", label: "Articles" },
    { value: "moment", label: "Moments" },
    { value: "author", label: "Authors" },
];

const SORTS = [
    { value: "relevance", label: "Relevance" },
    { value: "newest", label: "Newest" },
    { value: "oldest", label: "Oldest" },
];

const DEFAULT_LIMIT = 20;

function parseNonNegativeInt(value, fallback) {
    const parsed = Number.parseInt(value || "", 10);
    if (Number.isNaN(parsed) || parsed < 0) {
        return fallback;
    }
    return parsed;
}

function SearchResults() {
    const [searchParams, setSearchParams] = useSearchParams();

    const rawQuery = (searchParams.get("q") || "").trim();
    const rawType = searchParams.get("type");
    const type = SEARCH_TYPES.some((item) => item.value === rawType)
        ? rawType
        : "all";
    const sort = SORTS.some((item) => item.value === searchParams.get("sort"))
        ? searchParams.get("sort")
        : "relevance";
    const offset = parseNonNegativeInt(searchParams.get("offset"), 0);
    const limit = Math.min(Math.max(parseNonNegativeInt(searchParams.get("limit"), DEFAULT_LIMIT), 1), 100);

    const [inputValue, setInputValue] = useState(rawQuery);

    useEffect(() => {
        setInputValue(rawQuery);
    }, [rawQuery]);

    const updateSearchParams = useCallback((mutate, options = {}) => {
        const nextParams = new URLSearchParams(searchParams);
        mutate(nextParams);
        setSearchParams(nextParams, options);
    }, [searchParams, setSearchParams]);

    useEffect(() => {
        if (rawType && rawType === type) {
            return;
        }
        updateSearchParams((params) => {
            params.set("type", type);
        }, { replace: true });
    }, [rawType, type, updateSearchParams]);

    useEffect(() => {
        const normalizedQuery = inputValue.trim();
        if (normalizedQuery === rawQuery) {
            return undefined;
        }

        const timerId = window.setTimeout(() => {
            updateSearchParams((params) => {
                if (normalizedQuery) {
                    params.set("q", normalizedQuery);
                } else {
                    params.delete("q");
                }
                params.set("offset", "0");
                params.set("limit", String(limit));
            }, { replace: true });
        }, 350);

        return () => window.clearTimeout(timerId);
    }, [inputValue, rawQuery, limit, updateSearchParams]);

    const { isLoading, isError, error, data } = useQuery(
        async () => {
            if (!rawQuery) {
                return {
                    items: [],
                    offset,
                    limit,
                    has_more: false,
                };
            }

            const response = await SearchService.search({
                q: rawQuery,
                type,
                sort,
                offset,
                limit,
            });
            return response.data;
        },
        {
            keys: [rawQuery, type, sort, offset, limit],
        }
    );

    const items = data?.items || [];
    const hasMore = Boolean(data?.has_more);
    const errorMessage = isError
        ? (error?.response?.data?.detail || "Failed to load search results")
        : "";

    const activeTypeLabel = useMemo(
        () => SEARCH_TYPES.find((item) => item.value === type)?.label || "All",
        [type]
    );

    return (
        <main id="search-results-page">
            <section className="search-results-header">
                <h1>Search</h1>
                <p>Discover posts, articles, videos, moments, and creators.</p>
                <GlobalSearchInput
                    value={inputValue}
                    onChange={setInputValue}
                    onSubmit={(value) => {
                        updateSearchParams((params) => {
                            params.set("q", value);
                            params.set("offset", "0");
                            params.set("limit", String(limit));
                        });
                    }}
                    placeholder="Search by title, tags, text, or author"
                    autoFocus
                />
            </section>

            <section className="search-results-controls">
                <div className="search-type-filters" role="tablist" aria-label="Search filters">
                    {
                        SEARCH_TYPES.map((item) => (
                            <button
                                key={item.value}
                                type="button"
                                className={type === item.value ? "active" : ""}
                                onClick={() => {
                                    if (type === item.value) {
                                        return;
                                    }
                                    updateSearchParams((params) => {
                                        params.set("type", item.value);
                                        params.set("offset", "0");
                                    });
                                }}
                            >
                                {item.label}
                            </button>
                        ))
                    }
                </div>
                <label className="search-sort-control" htmlFor="search-sort-select">
                    <span>Sort</span>
                    <select
                        id="search-sort-select"
                        value={sort}
                        onChange={(event) => {
                            const nextSort = event.target.value;
                            updateSearchParams((params) => {
                                params.set("sort", nextSort);
                                params.set("offset", "0");
                            });
                        }}
                    >
                        {
                            SORTS.map((item) => (
                                <option key={item.value} value={item.value}>
                                    {item.label}
                                </option>
                            ))
                        }
                    </select>
                </label>
            </section>

            <section className="search-results-body">
                {
                    !rawQuery &&
                    <div className="search-results-state">
                        Enter a query to start searching.
                    </div>
                }
                {
                    isError &&
                    <div className="search-results-state error">
                        {errorMessage}
                    </div>
                }
                {
                    rawQuery && isLoading &&
                    <div className="search-results-loader">
                        <Loader />
                    </div>
                }
                {
                    rawQuery && !isLoading && !isError && items.length === 0 &&
                    <div className="search-results-state">
                        No results found for "{rawQuery}" in {activeTypeLabel}.
                    </div>
                }
                {
                    !isLoading && !isError && items.length > 0 &&
                    <>
                        <div className="search-results-list">
                            {
                                items.map((item, index) => {
                                    if (item.result_type === "content" && item.content) {
                                        return (
                                            <FeedContentCard
                                                key={`content-${item.content.content_id}-${index}`}
                                                item={item.content}
                                                removeItem={() => {}}
                                            />
                                        );
                                    }

                                    if (item.result_type === "author" && item.author) {
                                        return (
                                            <div className="search-author-result" key={`author-${item.author.user_id}-${index}`}>
                                                <UserListItem user={item.author} />
                                            </div>
                                        );
                                    }

                                    return null;
                                })
                            }
                        </div>

                        {
                            hasMore &&
                            <div className="search-results-pagination">
                                <button
                                    type="button"
                                    className="btn btn-secondary"
                                    onClick={() => {
                                        updateSearchParams((params) => {
                                            params.set("offset", String(offset + limit));
                                        });
                                    }}
                                >
                                    Load more
                                </button>
                            </div>
                        }
                    </>
                }
            </section>
        </main>
    );
}

export default SearchResults;
