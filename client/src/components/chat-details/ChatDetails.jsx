import { useCallback, useEffect, useState, useRef, useContext } from "react";
import { useParams, useNavigate, useSearchParams } from "react-router-dom";
import { io } from "socket.io-client";

import "./ChatDetails.css"

import { StoreContext } from "../..";
import AssetService from "../../service/AssetService";
import ChatService from "../../service/ChatService";

import NotFound from "../not-found/NotFound";

import Message from "../message/Message";
import { MESSAGE_REACTIONS } from "../message/messageReactions";
import Event from "../event/Event";
import {
    applyReactionEventToMessage,
    normalizeMessageReactions,
} from "./messageReactionState";

import ChatModal from "../chat-modal/ChatModal";
import Modal from "../modal/Modal";
import { getAvatarUrl } from "../../utils/avatar";
import {
    buildComposerAttachmentFromAsset,
    formatAttachmentSize,
    resolveAssetTypeForFile,
} from "../../utils/postAttachments";
import {
    buildSearchSnippet,
    splitHighlightedText,
} from "./searchHelpers";
import {
    getTypingIndicatorText,
    removeTypingUser,
    TYPING_START_THROTTLE_MS,
    TYPING_STATUS_TIMEOUT_MS,
    upsertTypingUser,
} from "./typingState";


const HISTORY_PAGE_SIZE = 50;


function getMaxCharsInLine(textarea, content) {
    if (!content) {
        return 1;
    }

    const context = document.createElement('canvas').getContext('2d');
    if (!context) {
        return 1;
    }
    const computedStyle = window.getComputedStyle(textarea);
    context.font = computedStyle.font;
    const width = context.measureText(content).width / content.length;
    return Math.max(Math.floor(textarea.clientWidth / width), 1);
}

function createClientMessageId() {
    if (window.crypto?.randomUUID) {
        return window.crypto.randomUUID();
    }

    return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function parseSocketPayload(data) {
    return typeof data === "string" ? JSON.parse(data) : data;
}

function normalizeTimelineItem(item, currentUserId) {
    if (item.item_type === "message") {
        return {
            type: "message",
            key: `message-${item.message_id || item.client_message_id}`,
            chatSeq: item.chat_seq,
            messageId: item.message_id,
            clientMessageId: item.client_message_id,
            userId: item.user_id,
            content: item.content,
            editedAt: item.edited_at,
            deletedAt: item.deleted_at,
            deletedBy: item.deleted_by,
            replyToMessageId: item.reply_to_message_id,
            replyPreview: normalizeReplyPreview(item.reply_preview),
            username: item.user_id === currentUserId ? "You" : item.user.username,
            createdAt: item.created_at,
            avatarUrl: item.user?.avatar?.small_url || null,
            attachments: normalizeMessageAttachments(item.attachments),
            sharedContent: normalizeSharedContent(item.shared_content),
            reactions: normalizeMessageReactions(item.reactions),
            status: "sent",
        };
    }

    if (item.item_type === "event") {
        return {
            type: "event",
            key: `event-${item.event_id}`,
            chatSeq: item.chat_seq,
            eventId: item.event_id,
            action: item.event_type,
            username: item.user.username,
            addedUserUsername: item.altered_user?.username || null,
        };
    }

    return null;
}

function normalizeReplyPreview(replyPreview) {
    if (!replyPreview) {
        return null;
    }

    return {
        messageId: replyPreview.message_id,
        senderDisplayName: replyPreview.sender_display_name,
        contentPreview: replyPreview.content_preview,
        deleted: replyPreview.deleted,
    };
}

function sortTimelineItems(items) {
    return [...items].sort((a, b) => {
        if (a.chatSeq == null && b.chatSeq == null) {
            return 0;
        }
        if (a.chatSeq == null) {
            return 1;
        }
        if (b.chatSeq == null) {
            return -1;
        }
        return a.chatSeq - b.chatSeq;
    });
}

function mergeTimelineItems(prevItems, nextItems) {
    const byKey = new Map();

    [...prevItems, ...nextItems].forEach((item) => {
        const keys = [
            item.key,
            item.messageId ? `message-${item.messageId}` : null,
            item.clientMessageId ? `client-message-${item.clientMessageId}` : null,
            item.eventId ? `event-${item.eventId}` : null,
        ].filter(Boolean);

        const existingKey = keys.find((key) => byKey.has(key));
        if (existingKey) {
            const merged = {
                ...byKey.get(existingKey),
                ...item,
            };
            keys.forEach((key) => byKey.set(key, merged));
            return;
        }

        keys.forEach((key) => byKey.set(key, item));
    });

    return sortTimelineItems(Array.from(new Set(byKey.values())));
}

function getTimelineBounds(items) {
    const seqs = items
        .map((item) => item.chatSeq)
        .filter((chatSeq) => chatSeq != null);

    if (seqs.length === 0) {
        return {
            oldestSeq: null,
            latestSeq: null,
        };
    }

    return {
        oldestSeq: Math.min(...seqs),
        latestSeq: Math.max(...seqs),
    };
}

function normalizeMessagePayload(msgData, currentUserId) {
    return {
        messageId: msgData.message_id,
        clientMessageId: msgData.client_message_id,
        chatSeq: msgData.chat_seq,
        userId: msgData.user_id,
        content: msgData.content,
        editedAt: msgData.edited_at,
        deletedAt: msgData.deleted_at,
        deletedBy: msgData.deleted_by,
        replyToMessageId: msgData.reply_to_message_id,
        replyPreview: normalizeReplyPreview(msgData.reply_preview),
        username: msgData.user_id === currentUserId ? "You" : msgData.username,
        createdAt: msgData.created_at,
        avatarUrl: msgData.avatar_small_url || null,
        attachments: normalizeMessageAttachments(msgData.attachments),
        sharedContent: normalizeSharedContent(msgData.shared_content),
        reactions: normalizeMessageReactions(msgData.reactions),
        status: "sent",
    };
}

function normalizeSharedContent(content) {
    if (!content) {
        return null;
    }

    return {
        content_id: content.content_id,
        content_type: content.content_type,
        title: content.title,
        excerpt: content.excerpt,
        post_content: content.post_content,
        description: content.description,
        caption: content.caption,
        canonical_path: content.canonical_path,
        cover: content.cover,
        media_attachments: content.media_attachments || [],
        user: content.user,
        published_at: content.published_at,
        created_at: content.created_at,
    };
}

function normalizeMessageAttachments(attachments = []) {
    return attachments.map((attachment) => ({
        asset_id: attachment.asset_id,
        asset_type: attachment.asset_type,
        mime_type: attachment.mime_type,
        file_kind: attachment.file_kind || "file",
        original_filename: attachment.original_filename || "Untitled file",
        size_bytes: attachment.size_bytes,
        preview_url: attachment.preview_url,
        original_url: attachment.original_url,
        poster_url: attachment.poster_url,
        download_url: attachment.download_url,
        stream_url: attachment.stream_url,
        is_audio: Boolean(attachment.is_audio),
        duration_ms: attachment.duration_ms || null,
        position: attachment.position || 0,
        uploadState: "ready",
    }));
}

function buildReplyPreviewFromMessage(messageItem) {
    return {
        messageId: messageItem.messageId,
        senderDisplayName: messageItem.username,
        contentPreview: messageItem.deletedAt ? "Message deleted" : messageItem.content,
        deleted: Boolean(messageItem.deletedAt),
    };
}

function normalizeSearchResult(item, currentUserId) {
    return {
        messageId: item.message_id,
        chatSeq: item.chat_seq,
        userId: item.user_id,
        username: item.user_id === currentUserId ? "You" : item.user?.username || "Unknown",
        content: item.content,
        editedAt: item.edited_at,
        deletedAt: item.deleted_at,
        createdAt: item.created_at,
        avatarUrl: item.user?.avatar?.small_url || null,
    };
}

function MessageSearchNavigator({
    item,
    query,
    total,
    offset,
    isJumping,
    currentUserAvatarUrl,
    onJump,
    onNavigateNewer,
    onNavigateOlder,
}) {
    const createdAtTime = item?.createdAt
        ? new Date(item.createdAt).toLocaleString()
        : "";
    const avatarSrc = item?.avatarUrl
        || (item?.username === "You" ? currentUserAvatarUrl || "/assets/profile.svg" : "/assets/profile.svg");
    const snippet = buildSearchSnippet(item?.content, query);
    const currentIndex = total > 0 ? Math.min(offset + 1, total) : 0;
    const hasNewer = offset > 0;
    const hasOlder = offset + 1 < total;

    return (
        <div className="chat-search-result">
            <button
                type="button"
                className={`chat-search-result-main${isJumping ? " loading" : ""}`}
                onClick={() => onJump(item)}
                disabled={isJumping}
            >
                <img
                    className="chat-search-result-avatar"
                    src={avatarSrc}
                    alt=""
                    onError={(event) => {
                        event.currentTarget.src = "/assets/profile.svg";
                    }}
                />
                <div className="chat-search-result-body">
                    <div className="chat-search-result-meta">
                        <span className="chat-search-result-user">{item?.username}</span>
                        <span className="chat-search-result-time">{createdAtTime}</span>
                    </div>
                    <div className="chat-search-result-snippet">
                        {splitHighlightedText(snippet, query).map((part, index) => (
                            part.highlighted ? (
                                <mark key={`${part.text}-${index}`}>{part.text}</mark>
                            ) : (
                                <span key={`${part.text}-${index}`}>{part.text}</span>
                            )
                        ))}
                    </div>
                </div>
            </button>
            <div className="chat-search-navigation">
                <button
                    type="button"
                    className="chat-search-button"
                    onClick={onNavigateNewer}
                    disabled={!hasNewer || isJumping}
                >
                    Newer
                </button>
                <div className="chat-search-counter">
                    {currentIndex ? `${currentIndex} / ${total}` : "0 / 0"}
                </div>
                <button
                    type="button"
                    className="chat-search-button"
                    onClick={onNavigateOlder}
                    disabled={!hasOlder || isJumping}
                >
                    Older
                </button>
            </div>
        </div>
    );
}


function ChatDetails() {
    const { store } = useContext(StoreContext);

    const navigate = useNavigate();
    const [searchParams, setSearchParams] = useSearchParams();

    const params = useParams();
    const activeSearchQuery = searchParams.get("messageSearch")?.trim() || "";
    const rawSearchOffset = Number.parseInt(searchParams.get("messageSearchOffset") || "0", 10);
    const searchOffset = Number.isNaN(rawSearchOffset) ? 0 : rawSearchOffset;

    const [isEditChatModalActive, setIsEditChatModalActive] = useState(false);

    const [isError, setIsError] = useState(false);

    const [chat, setChat] = useState({});

    const [chatItems, setChatItems] = useState([]);
    const [message, setMessage] = useState("");
    const [attachments, setAttachments] = useState([]);
    const [editingMessage, setEditingMessage] = useState(null);
    const [replyingToMessage, setReplyingToMessage] = useState(null);
    const [messageMenu, setMessageMenu] = useState(null);
    const [deleteMessageCandidate, setDeleteMessageCandidate] = useState(null);
    const [isDeletingMessage, setIsDeletingMessage] = useState(false);
    const [oldestSeq, setOldestSeq] = useState(null);
    const [, setLatestSeq] = useState(null);
    const [hasMoreHistory, setHasMoreHistory] = useState(true);
    const [isLoadingHistory, setIsLoadingHistory] = useState(false);
    const [typingUsers, setTypingUsers] = useState([]);
    const [searchInput, setSearchInput] = useState(activeSearchQuery);
    const [isSearchPanelOpen, setIsSearchPanelOpen] = useState(Boolean(activeSearchQuery));
    const [searchResult, setSearchResult] = useState(null);
    const [searchTotal, setSearchTotal] = useState(0);
    const [isSearchLoading, setIsSearchLoading] = useState(false);
    const [searchError, setSearchError] = useState("");
    const [focusedSearchMessageId, setFocusedSearchMessageId] = useState(null);
    const [jumpingToSearchMessageId, setJumpingToSearchMessageId] = useState(null);

    const socket = useRef(null);
    const messagesEndRef = useRef(null);
    const textareaRef = useRef(null);
    const fileInputRef = useRef(null);
    const searchInputRef = useRef(null);
    const latestSeqRef = useRef(null);
    const previousChatIdRef = useRef(null);
    const searchRequestIdRef = useRef(0);
    const chatItemsRef = useRef([]);
    const pendingPrependScrollRef = useRef(null);
    const shouldScrollBottomRef = useRef(false);
    const typingTimeoutsRef = useRef(new Map());
    const typingStateRef = useRef({
        isTyping: false,
        lastSentAt: 0,
    });
    const directMember = chat.chat_type === "direct"
        ? chat.members?.find((member) => member.user_id !== store.user.user_id)
        : null;
    const chatTitle = directMember?.username || chat.title;
    const chatImage = directMember ? getAvatarUrl(directMember, "small") : "../../../assets/chat.svg";
    const typingIndicatorText = getTypingIndicatorText(typingUsers, chat.chat_type);
    const currentUserAvatarUrl = getAvatarUrl(store.user, "small");
    const currentChatId = params.chatId?.startsWith("@") ? params.chatId.slice(1) : null;

    const markCurrentChatRead = useCallback(async (chatId) => {
        try {
            await ChatService.markChatRead(chatId);
        } catch (e) {
            console.log(e);
        }
    }, []);

    const applyHistoryItems = useCallback((items, { prepend = false, scrollToBottom = false } = {}) => {
        const normalizedItems = items
            .map((item) => normalizeTimelineItem(item, store.user.user_id))
            .filter(Boolean);

        if (prepend && messagesEndRef.current) {
            pendingPrependScrollRef.current = {
                scrollHeight: messagesEndRef.current.scrollHeight,
                scrollTop: messagesEndRef.current.scrollTop,
            };
        }

        shouldScrollBottomRef.current = scrollToBottom;
        setChatItems((prevItems) => mergeTimelineItems(prevItems, normalizedItems));
    }, [store.user.user_id]);

    const applyReactionEvent = useCallback((reactionEvent) => {
        setChatItems((items) => items.map((item) => applyReactionEventToMessage(
            item,
            reactionEvent,
            store.user.user_id,
        )));
    }, [store.user.user_id]);

    const clearSearchState = useCallback(() => {
        searchRequestIdRef.current += 1;
        setSearchResult(null);
        setSearchTotal(0);
        setSearchError("");
        setFocusedSearchMessageId(null);
        setJumpingToSearchMessageId(null);
        setIsSearchLoading(false);
    }, []);

    const scrollToMessage = useCallback((messageId) => {
        const target = document.getElementById(`message-${messageId}`);
        if (!target) {
            return;
        }

        target.scrollIntoView({
            behavior: "smooth",
            block: "center",
        });
    }, []);

    const focusSearchResult = useCallback(async (item) => {
        if (!chat.chat_id || !item?.messageId) {
            return;
        }

        setFocusedSearchMessageId(item.messageId);

        const isAlreadyLoaded = chatItemsRef.current.some((chatItem) => (
            chatItem.type === "message" && chatItem.messageId === item.messageId
        ));

        if (isAlreadyLoaded) {
            requestAnimationFrame(() => {
                scrollToMessage(item.messageId);
            });
            return;
        }

        if (item.chatSeq == null) {
            return;
        }

        setJumpingToSearchMessageId(item.messageId);
        const requestId = searchRequestIdRef.current;

        try {
            const afterSeq = Math.max(item.chatSeq - Math.floor(HISTORY_PAGE_SIZE / 2), 0);
            const res = await ChatService.getChatHistory(chat.chat_id, {
                after_seq: afterSeq,
                limit: HISTORY_PAGE_SIZE,
            });

            if (requestId !== searchRequestIdRef.current) {
                return;
            }

            applyHistoryItems(res.data);
            window.setTimeout(() => {
                if (requestId === searchRequestIdRef.current) {
                    scrollToMessage(item.messageId);
                }
            }, 0);
        } catch (e) {
            console.log(e);
        } finally {
            if (requestId === searchRequestIdRef.current) {
                setJumpingToSearchMessageId(null);
            }
        }
    }, [applyHistoryItems, chat.chat_id, scrollToMessage]);

    const syncSearchParams = useCallback((nextQuery, nextOffset = 0) => {
        const nextParams = new URLSearchParams(searchParams);
        if (nextQuery) {
            nextParams.set("messageSearch", nextQuery);
            nextParams.set("messageSearchOffset", String(nextOffset));
        } else {
            nextParams.delete("messageSearch");
            nextParams.delete("messageSearchOffset");
        }
        setSearchParams(nextParams, { replace: true });
    }, [searchParams, setSearchParams]);

    const handleSearchSubmit = useCallback(() => {
        const nextQuery = searchInput.trim();
        setIsSearchPanelOpen(true);
        if (!nextQuery) {
            setSearchInput("");
            clearSearchState();
            syncSearchParams("", 0);
            return;
        }

        setSearchInput(nextQuery);
        if (nextQuery === activeSearchQuery && searchOffset === 0) {
            return;
        }

        clearSearchState();
        syncSearchParams(nextQuery, 0);
    }, [activeSearchQuery, clearSearchState, searchInput, searchOffset, syncSearchParams]);

    const handleSearchClear = useCallback(() => {
        setSearchInput("");
        clearSearchState();
        syncSearchParams("", 0);
        searchInputRef.current?.focus();
    }, [clearSearchState, syncSearchParams]);

    const handleSearchInputKeyDown = useCallback((event) => {
        if (event.key === "Enter") {
            event.preventDefault();
            handleSearchSubmit();
        }
    }, [handleSearchSubmit]);

    const handleSearchMoveNewer = useCallback(() => {
        if (!activeSearchQuery || searchOffset <= 0) {
            return;
        }
        syncSearchParams(activeSearchQuery, searchOffset - 1);
    }, [activeSearchQuery, searchOffset, syncSearchParams]);

    const handleSearchMoveOlder = useCallback(() => {
        if (!activeSearchQuery || searchTotal <= 0 || searchOffset + 1 >= searchTotal) {
            return;
        }
        syncSearchParams(activeSearchQuery, searchOffset + 1);
    }, [activeSearchQuery, searchOffset, searchTotal, syncSearchParams]);

    const updateMessageInChat = useCallback((messageItem) => {
        setChatItems(items => items.map((item) => (
            item.type === "message" && item.messageId === messageItem.messageId
                ? {
                    ...item,
                    ...messageItem,
                    key: item.key,
                }
                : item.type === "message" && item.replyToMessageId === messageItem.messageId
                    ? {
                        ...item,
                        replyPreview: buildReplyPreviewFromMessage(messageItem),
                    }
                : item
        )));
    }, []);

    const clearTypingTimers = useCallback(() => {
        typingTimeoutsRef.current.forEach((timeoutId) => {
            window.clearTimeout(timeoutId);
        });
        typingTimeoutsRef.current.clear();
    }, []);

    const resetTypingState = useCallback(() => {
        clearTypingTimers();
        typingStateRef.current.isTyping = false;
        typingStateRef.current.lastSentAt = 0;
        setTypingUsers([]);
    }, [clearTypingTimers]);

    const stopTyping = useCallback(() => {
        if (!typingStateRef.current.isTyping) {
            return;
        }

        typingStateRef.current.isTyping = false;
        typingStateRef.current.lastSentAt = 0;

        if (!socket.current?.connected || !chat.chat_id) {
            return;
        }

        socket.current.emit("typing:stop", {
            chat_id: chat.chat_id,
        });
    }, [chat.chat_id]);

    const scheduleTypingTimeout = useCallback((userId, expiresInSeconds = TYPING_STATUS_TIMEOUT_MS / 1000) => {
        const existingTimeout = typingTimeoutsRef.current.get(userId);
        if (existingTimeout) {
            window.clearTimeout(existingTimeout);
        }

        const timeoutId = window.setTimeout(() => {
            typingTimeoutsRef.current.delete(userId);
            setTypingUsers((users) => removeTypingUser(users, userId));
        }, Math.max(expiresInSeconds, 1) * 1000);

        typingTimeoutsRef.current.set(userId, timeoutId);
    }, []);

    const handleTypingStartEvent = useCallback((data) => {
        const typingData = parseSocketPayload(data);
        if (typingData.chat_id !== chat.chat_id || typingData.user_id === store.user.user_id) {
            return;
        }

        setTypingUsers((users) => upsertTypingUser(users, {
            userId: typingData.user_id,
            username: typingData.username,
        }));
        scheduleTypingTimeout(typingData.user_id, typingData.expires_in_seconds);
    }, [chat.chat_id, scheduleTypingTimeout, store.user.user_id]);

    const handleTypingStopEvent = useCallback((data) => {
        const typingData = parseSocketPayload(data);
        if (typingData.chat_id !== chat.chat_id || typingData.user_id === store.user.user_id) {
            return;
        }

        const existingTimeout = typingTimeoutsRef.current.get(typingData.user_id);
        if (existingTimeout) {
            window.clearTimeout(existingTimeout);
            typingTimeoutsRef.current.delete(typingData.user_id);
        }

        setTypingUsers((users) => removeTypingUser(users, typingData.user_id));
    }, [chat.chat_id, store.user.user_id]);

    useEffect(() => {
        setSearchInput(activeSearchQuery);
        if (activeSearchQuery) {
            setIsSearchPanelOpen(true);
        }
    }, [activeSearchQuery]);

    useEffect(() => {
        if (previousChatIdRef.current && previousChatIdRef.current !== currentChatId) {
            clearSearchState();
            setSearchInput("");
            setIsSearchPanelOpen(false);
            const nextParams = new URLSearchParams(searchParams);
            nextParams.delete("messageSearch");
            nextParams.delete("messageSearchOffset");
            setSearchParams(nextParams, { replace: true });
        }

        previousChatIdRef.current = currentChatId;
    }, [clearSearchState, currentChatId, searchParams, setSearchParams]);

    useEffect(() => {
        if (!chat.chat_id) {
            setSearchResult(null);
            setSearchTotal(0);
            setSearchError("");
            setIsSearchLoading(false);
            return;
        }

        if (!activeSearchQuery) {
            setSearchResult(null);
            setSearchTotal(0);
            setSearchError("");
            setIsSearchLoading(false);
            return;
        }

        let cancelled = false;
        const normalizedQuery = activeSearchQuery;
        const requestId = ++searchRequestIdRef.current;
        setSearchResult(null);
        setFocusedSearchMessageId(null);
        setJumpingToSearchMessageId(null);

        setIsSearchLoading(true);
        setSearchError("");

        const loadSearchResults = async () => {
            try {
                const res = await ChatService.searchChatMessages(chat.chat_id, {
                    query: normalizedQuery,
                    offset: searchOffset,
                    limit: 1,
                });
                if (cancelled) {
                    return;
                }

                const total = res.data.total || 0;
                if (total > 0 && searchOffset >= total) {
                    syncSearchParams(normalizedQuery, total - 1);
                    return;
                }

                const nextSearchResult = res.data.items?.[0]
                    ? normalizeSearchResult(res.data.items[0], store.user.user_id)
                    : null;
                if (requestId !== searchRequestIdRef.current) {
                    return;
                }

                setSearchTotal(total);
                setSearchResult(nextSearchResult);
                setFocusedSearchMessageId(nextSearchResult?.messageId || null);

                if (nextSearchResult) {
                    await focusSearchResult(nextSearchResult);
                } else {
                    setJumpingToSearchMessageId(null);
                }
            } catch (e) {
                if (!cancelled && requestId === searchRequestIdRef.current) {
                    console.log(e);
                    setSearchError("Failed to search messages");
                    setSearchResult(null);
                    setSearchTotal(0);
                }
            } finally {
                if (!cancelled && requestId === searchRequestIdRef.current) {
                    setIsSearchLoading(false);
                }
            }
        };

        loadSearchResults();

        return () => {
            cancelled = true;
        };
    }, [activeSearchQuery, chat.chat_id, focusSearchResult, searchOffset, store.user.user_id, syncSearchParams]);

    useEffect(() => {
        if (isSearchPanelOpen) {
            requestAnimationFrame(() => {
                searchInputRef.current?.focus();
            });
        }
    }, [isSearchPanelOpen]);

    const emitTypingStart = useCallback((value) => {
        if (!socket.current?.connected || !chat.chat_id || editingMessage) {
            return;
        }

        if (!value.trim()) {
            return;
        }

        const now = Date.now();
        if (
            typingStateRef.current.isTyping
            && now - typingStateRef.current.lastSentAt < TYPING_START_THROTTLE_MS
        ) {
            return;
        }

        typingStateRef.current.isTyping = true;
        typingStateRef.current.lastSentAt = now;

        socket.current.emit("typing:start", {
            chat_id: chat.chat_id,
        });
    }, [chat.chat_id, editingMessage]);

    useEffect(() => {
        const bounds = getTimelineBounds(chatItems);
        chatItemsRef.current = chatItems;
        setOldestSeq(bounds.oldestSeq);
        setLatestSeq(bounds.latestSeq);
        latestSeqRef.current = bounds.latestSeq;

        if (pendingPrependScrollRef.current && messagesEndRef.current) {
            const previousScroll = pendingPrependScrollRef.current;
            pendingPrependScrollRef.current = null;
            requestAnimationFrame(() => {
                if (!messagesEndRef.current) {
                    return;
                }
                messagesEndRef.current.scrollTop =
                    messagesEndRef.current.scrollHeight -
                    previousScroll.scrollHeight +
                    previousScroll.scrollTop;
            });
            return;
        }

        if (shouldScrollBottomRef.current && messagesEndRef.current) {
            shouldScrollBottomRef.current = false;
            requestAnimationFrame(() => {
                if (!messagesEndRef.current) {
                    return;
                }
                messagesEndRef.current.scroll({
                    top: messagesEndRef.current.scrollHeight,
                    behavior: 'auto',
                });
            });
        }
    }, [chatItems]);

    useEffect(() => {
        const fetchChat = async () => {
            try {
                const chatId = params.chatId.slice(1);
                if (!chatId) {
                    setIsError(true);
                    return;
                }

                const res = await ChatService.getChatById(chatId);

                setChat(res.data);

            } catch (e) {
                console.log(e);
                setIsError(true);
            }
        }

        fetchChat();
    }, [params.chatId])

    useEffect(() => {
        if (!chat.chat_id) {
            return;
        }

        markCurrentChatRead(chat.chat_id);
    }, [chat.chat_id, markCurrentChatRead]);

    useEffect(() => {
        const checkJoinedWrapper = async () => {
            try {
                const chatId = params.chatId.slice(1);
                if (!chatId) {
                    setIsError(true);
                    return;
                }

                const joined = await ChatService.getUserJoinedChats({ user_id: store.user.user_id });
                const isJoined = joined.data.some((ch) => ch.chat_id === chatId);
                const chatFooter = document.getElementById("chat-footer");
                const joinButton = document.getElementById("join-btn");

                if (isJoined || chat.chat_type === "direct") {
                    chatFooter?.classList.remove("hidden");
                    joinButton?.classList.add("hidden");
                } else {
                    chatFooter?.classList.add("hidden");
                    joinButton?.classList.remove("hidden");
                }
            } catch (e) {
                console.log(e);
                setIsError(true);
            }
        }

        checkJoinedWrapper();
    }, [params.chatId, store.user, chat])

    const loadOlderHistory = useCallback(async () => {
        if (!chat.chat_id || oldestSeq == null || isLoadingHistory || !hasMoreHistory) {
            return;
        }

        try {
            setIsLoadingHistory(true);
            const res = await ChatService.getChatHistory(chat.chat_id, {
                before_seq: oldestSeq,
                limit: HISTORY_PAGE_SIZE,
            });

            if (res.data.length < HISTORY_PAGE_SIZE) {
                setHasMoreHistory(false);
            }

            applyHistoryItems(res.data, { prepend: true });
        } catch (e) {
            console.log(e);
            setIsError(true);
        } finally {
            setIsLoadingHistory(false);
        }
    }, [applyHistoryItems, chat.chat_id, hasMoreHistory, isLoadingHistory, oldestSeq]);

    const handleHistoryScroll = useCallback(() => {
        if (messagesEndRef.current?.scrollTop === 0) {
            loadOlderHistory();
        }
    }, [loadOlderHistory]);

    useEffect(() => {
        const getHistoryWrapper = async () => {
            try {
                clearChat();
                setOldestSeq(null);
                setLatestSeq(null);
                latestSeqRef.current = null;
                setHasMoreHistory(true);

                const chatId = params.chatId.slice(1);
                if (!chatId) {
                    setIsError(true);
                    return;
                }

                const items = await ChatService.getChatHistory(chatId, {
                    limit: HISTORY_PAGE_SIZE,
                });

                setHasMoreHistory(items.data.length >= HISTORY_PAGE_SIZE);
                applyHistoryItems(items.data, { scrollToBottom: true });
            } catch (e) {
                console.log(e);
                setIsError(true);
            }
        }

        getHistoryWrapper();
    }, [applyHistoryItems, params.chatId]);

    useEffect(() => {
        if (!chat.chat_id) {
            return;
        }

        resetTypingState();
        socket.current = io(process.env.REACT_APP_WS_HOST, {
            path: "/ws",
            transports: ["websocket"],
            upgrade: false,
            auth: {
                token: localStorage.getItem("token"),
            },
        });

        const syncMissedItems = async () => {
            if (latestSeqRef.current == null) {
                return;
            }

            try {
                const res = await ChatService.getChatHistory(chat.chat_id, {
                    after_seq: latestSeqRef.current,
                    limit: HISTORY_PAGE_SIZE,
                });
                applyHistoryItems(res.data, { scrollToBottom: true });
            } catch (e) {
                console.log(e);
            }
        };

        socket.current.on("connect", () => {
            socket.current.emit("join", {
                chat_id: chat.chat_id,
            }, (response) => {
                if (response && !response.ok) {
                    console.log(response.error?.detail || "Failed to join chat");
                    return;
                }
                syncMissedItems();
            });
        });

        socket.current.on("connect_error", (error) => {
            console.log(error);
            setIsError(true);
        });

        socket.current.on("message:created", (data) => {
            const msgData = parseSocketPayload(data);
            addMessageToChat(normalizeMessagePayload(msgData, store.user.user_id));
            markCurrentChatRead(msgData.chat_id);
        })

        socket.current.on("message:updated", (data) => {
            const msgData = parseSocketPayload(data);
            updateMessageInChat(normalizeMessagePayload(msgData, store.user.user_id));
        })

        socket.current.on("message:deleted", (data) => {
            const msgData = parseSocketPayload(data);
            updateMessageInChat(normalizeMessagePayload(msgData, store.user.user_id));
        })

        socket.current.on("message:reaction:added", (data) => {
            const reactionEvent = parseSocketPayload(data);
            applyReactionEvent(reactionEvent);
        })

        socket.current.on("message:reaction:removed", (data) => {
            const reactionEvent = parseSocketPayload(data);
            applyReactionEvent(reactionEvent);
        })

        socket.current.on("typing:start", handleTypingStartEvent);
        socket.current.on("typing:stop", handleTypingStopEvent);

        return () => {
            stopTyping();
            resetTypingState();
            socket.current.emit("leave", {
                chat_id: chat.chat_id,
            });
            socket.current.off("connect");
            socket.current.off("message:created");
            socket.current.off("message:updated");
            socket.current.off("message:deleted");
            socket.current.off("message:reaction:added");
            socket.current.off("message:reaction:removed");
            socket.current.off("typing:start");
            socket.current.off("typing:stop");
            socket.current.off("connect_error");
            socket.current.disconnect();
        }
    }, [
        applyHistoryItems,
        applyReactionEvent,
        chat.chat_id,
        handleTypingStartEvent,
        handleTypingStopEvent,
        markCurrentChatRead,
        resetTypingState,
        stopTyping,
        store.user.user_id,
        updateMessageInChat,
    ]);

    const resizeTextarea = (value = textareaRef.current?.value || "") => {
        if (!textareaRef.current) {
            return;
        }

        let rowsTotalHeight = value.split("\n").length * 25;
        let symbolsTotalLength = Math.max(
            Math.ceil(value.length / getMaxCharsInLine(textareaRef.current, value)), 1
        ) * 25;

        textareaRef.current.style.height = `${Math.min(
            symbolsTotalLength ? Math.max(rowsTotalHeight, symbolsTotalLength) : rowsTotalHeight,
            200
        )
            }px`;

        messagesEndRef.current?.scroll({
            top: messagesEndRef.current.scrollHeight,
            behavior: 'smooth',
        });
    }

    const clearChat = () => {
        setChatItems([]);
    }

    const addMessageToChat = (messageItem) => {
        const nextItem = {
            type: "message",
            key: messageItem.messageId
                ? `message-${messageItem.messageId}`
                : `client-message-${messageItem.clientMessageId}`,
            ...messageItem,
        };

        shouldScrollBottomRef.current = true;
        setChatItems(items => mergeTimelineItems(items, [nextItem]));
    }

    const markMessageFailed = (clientMessageId) => {
        setChatItems(items => items.map((item) => (
            item.type === "message" && item.clientMessageId === clientMessageId
                ? { ...item, status: "failed" }
                : item
        )));
    }

    const sendMessagePayload = (pendingMessage) => {
        socket.current.timeout(10000).emit("message", {
            chat_id: chat.chat_id,
            client_message_id: pendingMessage.clientMessageId,
            content: pendingMessage.content,
            reply_to_message_id: pendingMessage.replyToMessageId || null,
            asset_ids: pendingMessage.attachments
                .filter((attachment) => attachment.uploadState === "ready" && attachment.asset_id)
                .map((attachment) => attachment.asset_id),
        }, (error, response) => {
            if (error || !response || !response.ok) {
                console.log(response?.error?.detail || "Failed to send message");
                markMessageFailed(pendingMessage.clientMessageId);
                return;
            }

            const msgData = response.data;
            addMessageToChat(normalizeMessagePayload(msgData, store.user.user_id));
            markCurrentChatRead(msgData.chat_id);
        });
    }

    const retryMessage = (clientMessageId) => {
        const failedMessage = chatItems.find((item) => (
            item.type === "message" && item.clientMessageId === clientMessageId
        ));
        if (!failedMessage) {
            return;
        }

        addMessageToChat({ ...failedMessage, status: "pending" });
        sendMessagePayload(failedMessage);
    }

    const clearComposer = () => {
        stopTyping();
        setMessage("");
        setAttachments([]);
        setEditingMessage(null);
        setReplyingToMessage(null);
        if (fileInputRef.current) {
            fileInputRef.current.value = "";
        }
        if (textareaRef.current) {
            textareaRef.current.value = "";
            textareaRef.current.style.height = "25px";
        }
    }

    const updateMessage = () => {
        const trimmedMessage = message.trim();
        if (!editingMessage || trimmedMessage === "") {
            textareaRef.current.focus();
            return;
        }

        socket.current.timeout(10000).emit("message:update", {
            message_id: editingMessage.messageId,
            content: trimmedMessage,
        }, (error, response) => {
            if (error || !response || !response.ok) {
                console.log(response?.error?.detail || "Failed to update message");
                return;
            }

            updateMessageInChat(normalizeMessagePayload(response.data, store.user.user_id));
            clearComposer();
        });
    }

    const uploadAttachment = async (file) => {
        const localId = `local-${Date.now()}-${Math.random().toString(16).slice(2)}`;
        const pendingAttachment = {
            id: localId,
            original_filename: file.name,
            size_bytes: file.size,
            file_kind: resolveAssetTypeForFile(file),
            uploadState: "uploading",
            error: "",
        };

        setAttachments((items) => [...items, pendingAttachment]);
        try {
            const initRes = await AssetService.initUpload({
                filename: file.name,
                size_bytes: file.size,
                declared_mime_type: file.type || null,
                asset_type: resolveAssetTypeForFile(file),
                usage_context: "message_attachment",
            });
            const uploadRes = await AssetService.uploadFile(
                initRes.data.upload_url,
                file,
                initRes.data.upload_headers || {},
            );
            if (!uploadRes.ok) {
                throw new Error("Upload failed");
            }

            const finalizeRes = await AssetService.finalizeUpload(initRes.data.asset.asset_id);
            const attachment = buildComposerAttachmentFromAsset(
                finalizeRes.data.asset,
                "file",
                file.name,
            );
            setAttachments((items) => items.map((item) => (
                item.id === localId ? { ...attachment, id: localId } : item
            )));
        } catch (e) {
            console.log(e);
            setAttachments((items) => items.map((item) => (
                item.id === localId
                    ? { ...item, uploadState: "failed", error: "Upload failed" }
                    : item
            )));
        }
    }

    const handleAttachmentSelect = (event) => {
        const files = Array.from(event.target.files || []);
        files.forEach(uploadAttachment);
        event.target.value = "";
    }

    const removeAttachment = (attachmentId) => {
        setAttachments((items) => items.filter((item) => item.id !== attachmentId));
    }

    const sendMessage = () => {
        if (editingMessage) {
            updateMessage();
            return;
        }

        const trimmedMessage = message.trim();
        const readyAttachments = attachments.filter((attachment) => (
            attachment.uploadState === "ready" && attachment.asset_id
        ));
        const hasUploadingAttachments = attachments.some((attachment) => attachment.uploadState === "uploading");
        if (hasUploadingAttachments) {
            return;
        }

        if (trimmedMessage !== "" || readyAttachments.length > 0) {
            const pendingMessage = {
                clientMessageId: createClientMessageId(),
                userId: store.user.user_id,
                content: trimmedMessage,
                attachments: readyAttachments,
                replyToMessageId: replyingToMessage?.messageId || null,
                replyPreview: replyingToMessage ? buildReplyPreviewFromMessage(replyingToMessage) : null,
                username: "You",
                createdAt: new Date().toISOString(),
                avatarUrl: store.user?.avatar?.small_url || null,
                sharedContent: null,
                status: "pending",
            };

            addMessageToChat(pendingMessage);
            sendMessagePayload(pendingMessage);

            clearComposer();
        } else {
            textareaRef.current.focus()
        }
    }

    const handleKeyDown = (event) => {
        if (event.shiftKey && event.key === 'Enter' && message.trim() !== "") {
            return;
        }
        else if (event.key === 'Enter' && (message.trim() !== "" || attachments.length > 0)) {
            sendMessage();
            event.preventDefault();
            resizeTextarea();
        }
    };

    const handleMessageChange = (event) => {
        const nextValue = event.target.value;
        setMessage(nextValue);
        resizeTextarea(nextValue);

        if (editingMessage) {
            return;
        }

        if (nextValue.trim()) {
            emitTypingStart(nextValue);
            return;
        }

        stopTyping();
    };

    const handleMessageBlur = () => {
        stopTyping();
    };

    const handleChatJoin = async () => {
        try {
            await ChatService.joinChat(chat.chat_id);
            navigate("/chats");

        } catch (e) {
            console.log(e);
        }
    }

    const handleChatLeave = async () => {
        try {
            stopTyping();
            await ChatService.leaveChat(chat.chat_id);
            navigate("/chats");

        } catch (e) {
            console.log(e);
        }
    }

    const optionsHandler = () => {
        const menu = document.getElementById('options');
        menu.style.display = (menu.style.display === 'none' || menu.style.display === '') ? 'flex' : 'none';
    }

    const handleChatDelete = async () => {
        try {
            stopTyping();
            await ChatService.deleteChat(chat.chat_id);
            navigate("/chats");
        } catch (e) {
            console.log(e);
        }
    }

    const openMessageMenu = (event, item) => {
        if (!item.messageId || item.status !== "sent") {
            return;
        }

        event.preventDefault();
        setMessageMenu({
            x: event.clientX,
            y: event.clientY,
            message: item,
        });
    }

    const startEditingMessage = () => {
        if (!messageMenu?.message) {
            return;
        }

        stopTyping();
        setEditingMessage(messageMenu.message);
        setReplyingToMessage(null);
        setMessage(messageMenu.message.content);
        setMessageMenu(null);
        requestAnimationFrame(() => {
            textareaRef.current?.focus();
            resizeTextarea();
        });
    }

    const requestDeleteSelectedMessage = () => {
        if (!messageMenu?.message) {
            return;
        }

        setDeleteMessageCandidate(messageMenu.message);
        setMessageMenu(null);
    }

    const startReplyingToMessage = () => {
        if (!messageMenu?.message) {
            return;
        }

        setReplyingToMessage(messageMenu.message);
        setEditingMessage(null);
        setMessageMenu(null);
        requestAnimationFrame(() => {
            textareaRef.current?.focus();
        });
    }

    const closeDeleteMessageModal = () => {
        if (!isDeletingMessage) {
            setDeleteMessageCandidate(null);
        }
    }

    const deleteSelectedMessage = () => {
        if (!deleteMessageCandidate) {
            return;
        }

        const messageId = deleteMessageCandidate.messageId;
        setIsDeletingMessage(true);
        socket.current.timeout(10000).emit("message:delete", {
            message_id: messageId,
        }, (error, response) => {
            setIsDeletingMessage(false);
            if (error || !response || !response.ok) {
                console.log(response?.error?.detail || "Failed to delete message");
                return;
            }

            updateMessageInChat(normalizeMessagePayload(response.data, store.user.user_id));
            setDeleteMessageCandidate(null);
            if (editingMessage?.messageId === messageId) {
                clearComposer();
            }
        });
    }

    const handleMessageReaction = (messageItem, reactionType) => {
        if (!messageItem?.messageId || messageItem.status !== "sent" || messageItem.deletedAt) {
            return;
        }

        const currentReaction = messageItem.reactions?.find((reaction) => reaction.reactedByMe)?.reactionType || null;
        const eventName = currentReaction === reactionType
            ? "message:reaction:remove"
            : "message:reaction:set";

        socket.current.timeout(10000).emit(eventName, {
            message_id: messageItem.messageId,
            reaction_type: reactionType,
        }, (error, response) => {
            if (error || !response || !response.ok) {
                console.log(response?.error?.detail || "Failed to update message reaction");
                return;
            }

            updateMessageInChat(normalizeMessagePayload(response.data, store.user.user_id));
        });
    }

    const handleMessageContextReaction = (reactionType) => {
        if (!messageMenu?.message) {
            return;
        }

        const selectedMessage = messageMenu.message;
        setMessageMenu(null);
        handleMessageReaction(selectedMessage, reactionType);
    }

    const setTitle = (newTitle) => {
        setChat((prev) => ({
            ...prev,
            title: newTitle,
        }))
    }

    if (isError) {
        return (
            <div className="chat-details">
                <NotFound />
            </div>
        )
    }

    return (
        <div className="chat-details" onClick={() => setMessageMenu(null)}>
            <div className="chat-header">
                <div className="header-label">
                    <img
                        src={chatImage}
                        alt=""
                        onError={(event) => {
                            event.currentTarget.src = "../../../assets/chat.svg";
                        }}
                    />
                    <h2><span id="ws-id">{chatTitle}</span></h2>
                </div>

                <div className="header-actions">
                    <button
                        type="button"
                        className={`header-action-button${isSearchPanelOpen ? " active" : ""}`}
                        aria-label="Toggle message search"
                        aria-expanded={isSearchPanelOpen}
                        onClick={() => setIsSearchPanelOpen((current) => !current)}
                    >
                        <img src="../../../assets/search.svg" alt="" />
                    </button>
                    <img id="options-btn" src="../../../assets/options.svg" alt="Options" onClick={optionsHandler} />
                </div>
            </div>
            <div id="options">
                {
                    store.user.user_id === chat.owner_id && chat.chat_type !== "direct" &&
                    <>
                        <div className="option" onClick={() => setIsEditChatModalActive(true)}>
                            <img src="../../../assets/edit.svg" alt="Edit" />
                            <div>Edit info</div>
                        </div>
                        <hr />
                    </>
                }
                <div className="option danger" onClick={handleChatLeave}>
                    <img src="../../../assets/leave.svg" alt="Leave" />
                    <div>Leave chat</div>
                </div>
                {
                    store.user.user_id === chat.owner_id &&
                    <div className="option danger" onClick={handleChatDelete}>
                        <img src="../../../assets/delete.svg" alt="Delete" />
                        <div>Delete chat</div>
                    </div>
                }
            </div>

            {isSearchPanelOpen && (
                <div className="chat-search-panel">
                    <div className="chat-search-bar">
                        <input
                            ref={searchInputRef}
                            type="text"
                            className="chat-search-input"
                            placeholder="Search messages in this chat"
                            value={searchInput}
                            maxLength={200}
                            onChange={(event) => setSearchInput(event.target.value)}
                            onKeyDown={handleSearchInputKeyDown}
                        />
                        <button
                            type="button"
                            className="chat-search-button primary"
                            onClick={handleSearchSubmit}
                            disabled={!searchInput.trim()}
                        >
                            Search
                        </button>
                        <button
                            type="button"
                            className="chat-search-button"
                            onClick={handleSearchClear}
                            disabled={!searchInput.trim() && !activeSearchQuery}
                        >
                            Clear
                        </button>
                        <button
                            type="button"
                            className="chat-search-button"
                            onClick={() => setIsSearchPanelOpen(false)}
                        >
                            Close
                        </button>
                    </div>

                    {searchError && <div className="chat-search-status error">{searchError}</div>}
                    {!activeSearchQuery && !searchError && (
                        <div className="chat-search-status">Search messages, then use Newer and Older to move between matches.</div>
                    )}
                    {activeSearchQuery && (
                        <>
                            {isSearchLoading && (
                                <div className="chat-search-status">Searching messages...</div>
                            )}
                            {!isSearchLoading && searchTotal === 0 && !searchError && (
                                <div className="chat-search-status">No messages found.</div>
                            )}
                            {!isSearchLoading && searchResult && (
                                <MessageSearchNavigator
                                    item={searchResult}
                                    query={activeSearchQuery}
                                    total={searchTotal}
                                    offset={searchOffset}
                                    isJumping={jumpingToSearchMessageId === searchResult.messageId}
                                    currentUserAvatarUrl={currentUserAvatarUrl}
                                    onJump={focusSearchResult}
                                    onNavigateNewer={handleSearchMoveNewer}
                                    onNavigateOlder={handleSearchMoveOlder}
                                />
                            )}
                            {!isSearchLoading && searchTotal > 0 && !searchResult && !searchError && (
                                <div className="chat-search-status">Search result is unavailable.</div>
                            )}
                            {searchTotal > 0 && (
                                <div className="chat-search-status chat-search-status-meta">
                                    Newest messages first
                                </div>
                            )}
                        </>
                    )}
                </div>
            )}

            <div className="chat-body" ref={messagesEndRef} onScroll={handleHistoryScroll}>
                {
                    isLoadingHistory &&
                    <div className="history-loader">Loading history...</div>
                }
                {
                    chatItems.map((item, index) => {
                        if (item.type === "message") {
                            return (
                                <Message
                                    key={item.key || index}
                                    messageId={item.messageId}
                                    username={item.username}
                                    content={item.content}
                                    createdAt={item.createdAt}
                                    avatarUrl={item.avatarUrl}
                                    status={item.status}
                                    editedAt={item.editedAt}
                                    deletedAt={item.deletedAt}
                                    replyPreview={item.replyPreview}
                                    attachments={item.attachments}
                                    sharedContent={item.sharedContent}
                                    reactions={item.reactions}
                                    isHighlighted={focusedSearchMessageId === item.messageId}
                                    onContextMenu={(event) => openMessageMenu(event, item)}
                                    onReplyPreviewClick={scrollToMessage}
                                    onRetry={() => retryMessage(item.clientMessageId)}
                                />
                            )
                        } else if (item.type === "event") {
                            return (
                                <Event key={item.key || index} action={item.action} username={item.username} addedUserUsername={item.addedUserUsername} />
                            )
                        }

                        return null;
                    })
                }
            </div>
            {
                messageMenu &&
                <div
                    className="message-context-menu"
                    style={{ left: messageMenu.x, top: messageMenu.y }}
                    onClick={(event) => event.stopPropagation()}
                >
                    {!messageMenu.message.deletedAt && (
                        <>
                            <div className="message-context-menu-reactions" role="toolbar" aria-label="Message reactions">
                                {MESSAGE_REACTIONS.map((reaction) => {
                                    const isActive = messageMenu.message?.reactions?.some((item) => (
                                        item.reactedByMe && item.reactionType === reaction.reactionType
                                    ));

                                    return (
                                        <button
                                            key={reaction.reactionType}
                                            type="button"
                                            className={`message-context-menu-reaction ${isActive ? "active" : ""}`}
                                            aria-label={reaction.ariaLabel}
                                            title={reaction.ariaLabel}
                                            onClick={() => handleMessageContextReaction(reaction.reactionType)}
                                        >
                                            <span aria-hidden="true">{reaction.emoji}</span>
                                        </button>
                                    );
                                })}
                            </div>
                            <div className="message-context-menu-divider" />
                        </>
                    )}
                    <div className="message-context-menu-actions">
                        <button type="button" onClick={startReplyingToMessage}>Reply</button>
                        {
                            messageMenu.message.userId === store.user.user_id && !messageMenu.message.deletedAt &&
                            <>
                                <button type="button" onClick={startEditingMessage}>Edit</button>
                                <button type="button" className="danger" onClick={requestDeleteSelectedMessage}>Delete</button>
                            </>
                        }
                    </div>
                </div>
            }
            <Modal active={Boolean(deleteMessageCandidate)} setActive={closeDeleteMessageModal}>
                <div className="delete-message-modal">
                    <h2>Delete message?</h2>
                    <p>The message will stay in history as a deleted message stub.</p>
                    <div className="delete-message-modal-actions">
                        <button
                            type="button"
                            className="btn btn-secondary"
                            onClick={closeDeleteMessageModal}
                            disabled={isDeletingMessage}
                        >
                            Cancel
                        </button>
                        <button
                            type="button"
                            className="btn btn-danger"
                            onClick={deleteSelectedMessage}
                            disabled={isDeletingMessage}
                        >
                            {isDeletingMessage ? "Deleting..." : "Delete"}
                        </button>
                    </div>
                </div>
            </Modal>

            <div id="chat-footer" className="chat-footer">
                {
                    editingMessage &&
                    <div className="edit-banner">
                        <div>
                            <span>Editing message</span>
                            <p>{editingMessage.content}</p>
                        </div>
                        <button type="button" onClick={clearComposer}>Cancel</button>
                    </div>
                }
                {
                    replyingToMessage &&
                    <div className="reply-banner">
                        <div>
                            <span>Replying to {replyingToMessage.username}</span>
                            <p>{replyingToMessage.deletedAt ? "Message deleted" : replyingToMessage.content}</p>
                        </div>
                        <button type="button" onClick={() => setReplyingToMessage(null)}>Cancel</button>
                    </div>
                }
                {
                    attachments.length > 0 &&
                    <div className="composer-attachments">
                        {attachments.map((attachment) => (
                            <div
                                key={attachment.id || attachment.asset_id}
                                className={`composer-attachment composer-attachment-${attachment.uploadState}`}
                            >
                                <span className="composer-attachment-name">
                                    {attachment.original_filename || "Untitled file"}
                                </span>
                                <span className="composer-attachment-meta">
                                    {attachment.uploadState === "uploading"
                                        ? "Uploading"
                                        : attachment.uploadState === "failed"
                                            ? attachment.error || "Failed"
                                            : formatAttachmentSize(attachment.size_bytes)}
                                </span>
                                <button
                                    type="button"
                                    aria-label={`Remove ${attachment.original_filename || "attachment"}`}
                                    onClick={() => removeAttachment(attachment.id)}
                                >
                                    x
                                </button>
                            </div>
                        ))}
                    </div>
                }
                {
                    typingIndicatorText &&
                    <div className="typing-indicator" aria-live="polite">
                        {typingIndicatorText}
                    </div>
                }
                <div className="msg-box">
                    <button
                        type="button"
                        className="attach-button"
                        aria-label="Attach file"
                        disabled={Boolean(editingMessage)}
                        onClick={() => fileInputRef.current?.click()}
                    >
                        +
                    </button>
                    <input
                        ref={fileInputRef}
                        type="file"
                        multiple
                        className="attachment-input"
                        onChange={handleAttachmentSelect}
                    />
                    <textarea
                        name="message-input"
                        ref={textareaRef}
                        value={message}
                        placeholder={editingMessage ? "Edit message" : "Type a message"}
                        onChange={handleMessageChange}
                        onBlur={handleMessageBlur}
                        id="message-input"
                        onKeyDown={handleKeyDown}
                    >
                    </textarea>
                </div>
                <button className="btn btn-primary" onClick={sendMessage}>
                    <img src="../../../assets/send-message.svg" alt="" />
                </button>
            </div>
            {chat.chat_type !== "direct" && <button id="join-btn" className="btn btn-primary hidden" onClick={handleChatJoin}>Join</button>}

            <ChatModal
                key={"edit"}
                active={isEditChatModalActive}
                setActive={setIsEditChatModalActive}
                saveChatFunc={ChatService.updateChat}
                chatId={chat.chat_id}
                title={chat.title}
                setTitle={setTitle}
                isPrivate={chat.is_private}
                modalHeader={"Edit chat info"}
                buttonText={"Save"}
            />
        </div>
    )
}

export default ChatDetails;
