import { createRef, useEffect, useRef, useState } from "react";
import { useQuery } from "@siberiacancode/reactuse";

import "./ContentList.css";

import Loader from "../loader/Loader";


const ITEMS_IN_PORTION = 5;


function ContentList({
    fetchItems,
    filters,
    refresh,
    renderItem,
    emptyText = "Nothing here yet",
}) {
    const lastItem = createRef();
    const observerLoader = useRef();
    const filtersKey = JSON.stringify(filters || {});

    const [items, setItems] = useState([]);
    const [offset, setOffset] = useState(0);

    const removeItem = (itemId) => {
        setItems((prevItems) => prevItems.filter((item) => item.content_id !== itemId && item.article_id !== itemId));
    };

    useEffect(() => {
        setOffset(0);
        setItems([]);
    }, [refresh, filtersKey]);

    const { isLoading, isError, error } = useQuery(
        async () => {
            const params = {
                ...filters,
                offset,
                limit: ITEMS_IN_PORTION,
            };
            const res = await fetchItems(params);
            return res.data;
        },
        {
            keys: [offset, refresh, filtersKey],
            onSuccess: (fetchedItems) => {
                setItems((prevItems) => (
                    offset === 0
                        ? fetchedItems
                        : [...prevItems, ...fetchedItems]
                ));
            },
        }
    );

    useEffect(() => {
        if (observerLoader.current) {
            observerLoader.current.disconnect();
        }

        observerLoader.current = new IntersectionObserver((entries) => {
            if (entries[0].isIntersecting && offset < ITEMS_IN_PORTION * 10) {
                setOffset((prev) => prev + ITEMS_IN_PORTION);
            }
        });

        if (lastItem.current) {
            observerLoader.current.observe(lastItem.current);
        }
    }, [lastItem, offset]);

    if (isError) {
        console.log(error);
        return null;
    }

    return (
        <div className="content-list">
            <div className="content-list-items">
                {
                    items.map((item, index) => renderItem({
                        item,
                        removeItem,
                        ref: index + 1 === items.length ? lastItem : null,
                    }))
                }
                {
                    !isLoading && items.length === 0
                        ? <div className="content-list-empty">{emptyText}</div>
                        : null
                }
            </div>

            {
                isLoading &&
                <div className="content-list-loader">
                    <Loader />
                </div>
            }
        </div>
    );
}

export default ContentList;
