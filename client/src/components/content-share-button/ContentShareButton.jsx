import { useContext, useEffect, useMemo, useState } from "react";

import "./ContentShareButton.css";

import { StoreContext } from "../..";
import ContentService from "../../service/ContentService";
import Modal from "../modal/Modal";
import Loader from "../loader/Loader";
import { ShareIcon } from "../icons/ArticleUiIcons";
import { getAvatarUrl } from "../../utils/avatar";


function ContentShareButton({ contentId, contentTitle = "content", className = "" }) {
    const { store } = useContext(StoreContext);
    const [isModalActive, setIsModalActive] = useState(false);
    const [chats, setChats] = useState([]);
    const [selectedChatIds, setSelectedChatIds] = useState([]);
    const [isLoadingChats, setIsLoadingChats] = useState(false);
    const [isSharing, setIsSharing] = useState(false);
    const [error, setError] = useState("");
    const [success, setSuccess] = useState("");

    useEffect(() => {
        if (!isModalActive || !store.isAuthenticated) {
            return;
        }

        let isMounted = true;
        const loadChats = async () => {
            setIsLoadingChats(true);
            setError("");
            setSuccess("");
            try {
                const { default: ChatService } = await import("../../service/ChatService");
                const res = await ChatService.getUserJoinedChats({ limit: 100 });
                if (isMounted) {
                    setChats(res.data || []);
                }
            } catch (e) {
                console.log(e);
                if (isMounted) {
                    setError("Не удалось загрузить чаты");
                }
            } finally {
                if (isMounted) {
                    setIsLoadingChats(false);
                }
            }
        };

        loadChats();
        return () => {
            isMounted = false;
        };
    }, [isModalActive, store.isAuthenticated]);

    const selectedCount = selectedChatIds.length;
    const modalTitle = useMemo(() => `Поделиться: ${contentTitle || "контент"}`, [contentTitle]);

    const toggleChat = (chatId) => {
        setSelectedChatIds((items) => (
            items.includes(chatId)
                ? items.filter((item) => item !== chatId)
                : [...items, chatId]
        ));
        setError("");
        setSuccess("");
    };

    const closeModal = () => {
        if (isSharing) {
            return;
        }
        setIsModalActive(false);
        setSelectedChatIds([]);
        setError("");
        setSuccess("");
    };

    const shareContent = async () => {
        if (selectedChatIds.length === 0) {
            setError("Выберите хотя бы один чат");
            return;
        }

        setIsSharing(true);
        setError("");
        setSuccess("");
        try {
            await ContentService.shareToChats(contentId, selectedChatIds);
            setSuccess("Отправлено");
            setSelectedChatIds([]);
        } catch (e) {
            console.log(e);
            setError(e?.response?.data?.detail || "Не удалось отправить");
        } finally {
            setIsSharing(false);
        }
    };

    if (!store.isAuthenticated || !contentId) {
        return null;
    }

    return (
        <>
            <button
                type="button"
                className={`content-share-trigger ${className}`}
                onClick={() => setIsModalActive(true)}
            >
                <ShareIcon />
                <span>Поделиться</span>
            </button>

            <Modal active={isModalActive} setActive={closeModal}>
                <div className="content-share-modal">
                    <div className="content-share-header">
                        <h2>{modalTitle}</h2>
                    </div>

                    <div className="content-share-chat-list">
                        {isLoadingChats && <Loader />}
                        {!isLoadingChats && chats.length === 0 && (
                            <p className="content-share-empty">Нет доступных чатов</p>
                        )}
                        {!isLoadingChats && chats.map((chat) => (
                            <ShareChatOption
                                key={chat.chat_id}
                                chat={chat}
                                currentUserId={store.user.user_id}
                                selected={selectedChatIds.includes(chat.chat_id)}
                                onToggle={() => toggleChat(chat.chat_id)}
                            />
                        ))}
                    </div>

                    {error && <p className="content-share-error">{error}</p>}
                    {success && <p className="content-share-success">{success}</p>}

                    <div className="content-share-actions">
                        <button type="button" className="btn btn-secondary" onClick={closeModal} disabled={isSharing}>
                            Закрыть
                        </button>
                        <button
                            type="button"
                            className="btn btn-primary"
                            onClick={shareContent}
                            disabled={isSharing || selectedCount === 0}
                        >
                            {isSharing ? <Loader /> : `Отправить${selectedCount ? ` (${selectedCount})` : ""}`}
                        </button>
                    </div>
                </div>
            </Modal>
        </>
    );
}

function ShareChatOption({ chat, currentUserId, selected, onToggle }) {
    const directMember = chat.chat_type === "direct"
        ? chat.members?.find((member) => member.user_id !== currentUserId)
        : null;
    const title = chat.display_title || directMember?.username || chat.title;
    const imageSrc = chat.display_avatar?.small_url || (directMember ? getAvatarUrl(directMember, "small") : "../../../assets/chat.svg");

    return (
        <button
            type="button"
            className={`content-share-chat-option${selected ? " selected" : ""}`}
            onClick={onToggle}
        >
            <img
                src={imageSrc}
                alt={title}
                onError={(event) => {
                    event.currentTarget.src = "../../../assets/chat.svg";
                }}
            />
            <span>{title}</span>
            <span className="content-share-check" aria-hidden="true">{selected ? "✓" : ""}</span>
        </button>
    );
}

export default ContentShareButton;
