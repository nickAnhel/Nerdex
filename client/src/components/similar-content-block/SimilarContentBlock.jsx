import { useEffect, useState } from "react";

import "./SimilarContentBlock.css";

import FeedContentCard from "../feed-content-card/FeedContentCard";
import Loader from "../loader/Loader";
import ContentService from "../../service/ContentService";


function SimilarContentBlock({
    contentId,
    contentType = null,
    limit = 4,
    title = "Похожие публикации",
    hideOnError = true,
}) {
    const [items, setItems] = useState([]);
    const [isLoading, setIsLoading] = useState(false);
    const [isError, setIsError] = useState(false);

    useEffect(() => {
        if (!contentId) {
            setItems([]);
            setIsLoading(false);
            setIsError(false);
            return;
        }

        let cancelled = false;

        const fetchSimilar = async () => {
            setIsLoading(true);
            setIsError(false);
            try {
                const res = await ContentService.getSimilarContent(contentId, {
                    limit,
                    content_type: contentType,
                });
                if (cancelled) {
                    return;
                }
                setItems((res.data?.items || []).map((item) => item.content).filter(Boolean));
            } catch (error) {
                if (cancelled) {
                    return;
                }
                console.log(error);
                setIsError(true);
                setItems([]);
            } finally {
                if (!cancelled) {
                    setIsLoading(false);
                }
            }
        };

        fetchSimilar();

        return () => {
            cancelled = true;
        };
    }, [contentId, contentType, limit]);

    if (!contentId) {
        return null;
    }

    if (isError && hideOnError) {
        return null;
    }

    return (
        <section className="similar-content-block" aria-label={title}>
            <h3>{title}</h3>

            {
                isLoading
                    ? (
                        <div className="similar-content-state">
                            <Loader />
                        </div>
                    )
                    : null
            }

            {
                !isLoading && isError && !hideOnError
                    ? <div className="similar-content-state">Не удалось загрузить похожие публикации.</div>
                    : null
            }

            {
                !isLoading && !isError && items.length === 0
                    ? <div className="similar-content-state">Похожих публикаций пока нет.</div>
                    : null
            }

            {
                !isLoading && !isError && items.length > 0
                    ? (
                        <div className="similar-content-list">
                            {
                                items.map((item) => (
                                    <FeedContentCard
                                        key={item.content_id}
                                        item={item}
                                        removeItem={() => {}}
                                    />
                                ))
                            }
                        </div>
                    )
                    : null
            }
        </section>
    );
}

export default SimilarContentBlock;
